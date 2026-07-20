"""
core/executor.py

The Executor — receives a Plan and runs every Task in dependency order.

Single responsibility:
    Plan  →  execute each Task  →  Plan (all tasks in terminal states)

The Executor does NOT create plans. It only follows them.

Full execution flow per plan:
    1. Publish "plan.started" event
    2. Loop until all tasks are done:
        a. Find ready tasks (dependencies all COMPLETED)
        b. Skip any task whose dependency FAILED or was CANCELLED
        c. For each ready task:
             - Mark RUNNING + publish "task.started"
             - Dispatch to the correct tool via ToolManager
             - Wrap result in TaskResult
             - Mark COMPLETED or FAILED
             - Retry on failure (up to MAX_TASK_RETRIES)
             - Publish "task.completed" or "task.failed"
             - Store result in MemoryManager
        d. Update plan status
    3. Publish "plan.completed" or "plan.failed"
    4. Return the fully-executed Plan

Dependencies injected at construction (all optional — graceful if absent):
    tool_manager:   ToolManager    — dispatches tasks to the right tool
    memory_manager: MemoryManager  — stores task results for future retrieval
    event_bus:      EventBus       — publishes lifecycle events

Event names published:
    "plan.started"     → data: plan
    "plan.completed"   → data: plan
    "plan.failed"      → data: plan
    "task.started"     → data: task
    "task.completed"   → data: task
    "task.failed"      → data: task
    "task.skipped"     → data: task
    "task.retrying"    → data: {"task": task, "attempt": n}
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from config.settings import MAX_TASK_RETRIES
from core.progress_tracker import ProgressTracker
from models.enums import TaskStatus
from models.plan import Plan
from models.result import TaskResult
from models.task import Task
from utils.logger import logger

if TYPE_CHECKING:
    from core.events import EventBus
    from memory.memory_manager import MemoryManager
    from tools.tool_manager import ToolManager

# Tool name used when a task has no specific tool — treat as LLM pass-through
_LLM_TOOL = "llm"
_NO_TOOL   = None


class Executor:
    """
    Executes a Plan by running each Task in dependency order.

    All dependencies are optional — the Executor degrades gracefully if
    ToolManager or MemoryManager are not available.
    """

    def __init__(
        self,
        tool_manager:   ToolManager    | None = None,
        memory_manager: MemoryManager  | None = None,
        event_bus:      EventBus       | None = None,
    ) -> None:
        self._tools   = tool_manager
        self._memory  = memory_manager
        self._events  = event_bus

    # ── Public API ────────────────────────────────────────────────────────────

    def execute_plan(self, plan: Plan) -> Plan:
        """
        Execute all tasks in the plan in dependency order.

        Args:
            plan: A validated Plan produced by the Planner.

        Returns:
            The same Plan object with all tasks updated to terminal states.
        """
        if not plan.tasks:
            logger.warning("Executor: received empty plan — nothing to execute.")
            return plan

        tracker = ProgressTracker(plan)
        logger.info(f"Executor: starting plan '{plan.goal[:60]}'")
        plan.update_status()
        self._emit("plan.started", plan)

        # Safety guard: never loop more times than there are tasks
        max_iterations = len(plan.tasks) * (MAX_TASK_RETRIES + 2)
        iteration      = 0

        while not plan.is_finished():
            iteration += 1
            if iteration > max_iterations:
                logger.error(
                    "Executor: exceeded maximum iterations — "
                    "possible stuck plan. Cancelling remaining tasks."
                )
                for task in plan.tasks:
                    if not task.is_done():
                        task.mark_cancelled()
                break

            # Mark tasks whose dependencies failed as SKIPPED
            self._skip_blocked_tasks(plan, tracker)

            # Find tasks that are ready to run now
            ready = plan.next_ready_tasks()

            if not ready:
                # No tasks are ready and plan isn't finished → stuck
                if not plan.is_finished():
                    logger.error(
                        "Executor: no ready tasks but plan is not finished. "
                        "Cancelling remaining tasks."
                    )
                    for task in plan.tasks:
                        if not task.is_done():
                            task.mark_cancelled()
                break

            for task in ready:
                self.execute_task(task, plan, tracker)
                plan.update_status()

        plan.update_status()
        tracker.on_plan_complete()

        event = "plan.completed" if plan.is_successful() else "plan.failed"
        self._emit(event, plan)

        logger.info(f"Executor: {plan.summary()}")
        return plan

    def execute_task(
        self,
        task:    Task,
        plan:    Plan,
        tracker: ProgressTracker,
    ) -> TaskResult:
        """
        Execute a single task, with retry on failure.

        Args:
            task:    The Task to execute.
            plan:    The Plan this task belongs to (used for context).
            tracker: ProgressTracker for this plan run.

        Returns:
            The final TaskResult (success or failure after all retries).
        """
        last_result: TaskResult | None = None

        for attempt in range(1, MAX_TASK_RETRIES + 2):   # initial + retries
            if attempt > 1:
                logger.info(
                    f"Executor: retrying task [{task.id}] "
                    f"(attempt {attempt}/{MAX_TASK_RETRIES + 1})"
                )
                task.retries += 1
                self._emit("task.retrying", {"task": task, "attempt": attempt})

            # ── Mark running ──────────────────────────────────────────────────
            task.mark_running()
            tracker.on_task_start(task)
            self._emit("task.started", task)

            # ── Dispatch to tool ──────────────────────────────────────────────
            start_time = time.perf_counter()
            last_result = self._dispatch(task)
            elapsed     = round(time.perf_counter() - start_time, 4)

            # Stamp the actual execution time onto the result
            last_result = TaskResult(
                success        = last_result.success,
                output         = last_result.output,
                error          = last_result.error,
                tool           = last_result.tool,
                execution_time = elapsed,
                metadata       = last_result.metadata,
                timestamp      = last_result.timestamp,
            )

            # ── Handle outcome ────────────────────────────────────────────────
            if last_result.success:
                task.mark_completed(last_result)
                tracker.on_task_complete(task)
                self._emit("task.completed", task)
                self._store_result(task)
                logger.info(
                    f"Executor: task [{task.id}] completed "
                    f"in {elapsed:.3f}s — {task.description}"
                )
                return last_result

            # Failed this attempt
            logger.warning(
                f"Executor: task [{task.id}] attempt {attempt} failed — "
                f"{last_result.error}"
            )

        # All attempts exhausted
        task.mark_failed(last_result)
        tracker.on_task_failed(task)
        self._emit("task.failed", task)
        self._store_result(task)
        logger.error(
            f"Executor: task [{task.id}] failed after "
            f"{MAX_TASK_RETRIES + 1} attempt(s) — {task.error}"
        )
        return last_result

    # ── Private — scheduling ──────────────────────────────────────────────────

    def _skip_blocked_tasks(self, plan: Plan, tracker: ProgressTracker) -> None:
        """
        Mark PENDING/WAITING tasks as SKIPPED if any of their dependencies
        FAILED or were CANCELLED.

        A task cannot run if a required predecessor is in a terminal failure state.
        """
        bad_ids: set[int] = {
            t.id for t in plan.tasks
            if t.status in (TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.SKIPPED)
        }
        if not bad_ids:
            return

        for task in plan.tasks:
            if task.status in (TaskStatus.PENDING, TaskStatus.WAITING):
                if any(dep in bad_ids for dep in task.dependencies):
                    task.mark_skipped()
                    tracker.on_task_skipped(task)
                    self._emit("task.skipped", task)
                    logger.warning(
                        f"Executor: task [{task.id}] skipped — "
                        f"dependency in failed/cancelled/skipped state."
                    )

    # ── Private — tool dispatch ───────────────────────────────────────────────

    def _dispatch(self, task: Task) -> TaskResult:
        """
        Route the task to the appropriate handler and return a TaskResult.

        Routing logic:
            tool is None or "llm" → LLM pass-through (returns a note for now;
                                     full LLM integration happens in Workflow)
            tool is a known name  → ToolManager.execute_by_name()
            tool is unknown       → TaskResult.failure_result(...)
        """
        tool_name = (task.tool or "").strip().lower()

        # ── No tool / LLM pass-through ────────────────────────────────────────
        if not tool_name or tool_name == _LLM_TOOL:
            logger.debug(
                f"Executor: task [{task.id}] is an LLM/reasoning step — "
                f"no tool dispatch needed."
            )
            return TaskResult.success_result(
                output   = task.description,
                tool     = tool_name or "none",
                metadata = {"type": "reasoning"},
            )

        # ── Tool dispatch ─────────────────────────────────────────────────────
        if self._tools is None:
            return TaskResult.failure_result(
                error = "ToolManager not available.",
                tool  = tool_name,
            )

        if tool_name not in self._tools.tools:
            return TaskResult.failure_result(
                error = f"Unknown tool '{tool_name}'. "
                        f"Available: {sorted(self._tools.tools.keys())}",
                tool  = tool_name,
            )

        try:
            raw = self._tools.tools[tool_name].execute(task.description)
            return TaskResult.success_result(
                output = raw,
                tool   = tool_name,
            )
        except Exception as exc:
            logger.exception(
                f"Executor: tool '{tool_name}' raised an exception: {exc}"
            )
            return TaskResult.failure_result(
                error = str(exc),
                tool  = tool_name,
            )

    # ── Private — memory integration ──────────────────────────────────────────

    def _store_result(self, task: Task) -> None:
        """
        Persist the task result to memory so it can be retrieved later.
        Silently skips if MemoryManager is not available.
        """
        if self._memory is None or task.task_result is None:
            return
        try:
            summary = (
                f"Task [{task.id}] '{task.description}' "
                f"({task.status.value}): {task.output_text[:200]}"
            )
            self._memory.store_memory(summary)
            logger.debug(f"Executor: stored result for task [{task.id}].")
        except Exception as e:
            logger.warning(f"Executor: could not store result for task [{task.id}]: {e}")

    # ── Private — event bus ───────────────────────────────────────────────────

    def _emit(self, event_name: str, data: object = None) -> None:
        """Publish an event on the EventBus. Silently skips if bus is absent."""
        if self._events is None:
            return
        try:
            self._events.emit(event_name, data)
        except Exception as e:
            logger.warning(f"Executor: event '{event_name}' emit failed: {e}")
