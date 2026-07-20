"""
core/workflow.py

The Workflow Engine — the top-level orchestrator of IRIS.

Single responsibility:
    user goal (str)  →  WorkflowResult  (completed | failed | cancelled)

The WorkflowEngine is the only thing the IrisAssistant should call for
goal-directed tasks. It coordinates all other systems internally:

    User Goal
        │
        ▼
    Planner.create_plan()
        │
        ▼
    Executor.execute_plan()       ← runs tasks in dependency order
        │
        ▼
    ReflectionEngine.reflect()    ← evaluates result
        │
    ┌───┴──────────────────────────────────────────────────────┐
    │ CONTINUE → done                                          │
    │ RETRY    → reset failed tasks → Executor again           │
    │ REPLAN   → use new plan from reflection → loop again     │
    │ ABORT    → give up                                       │
    └──────────────────────────────────────────────────────────┘

Workflow lifecycle states:
    CREATED   → just built, not started
    RUNNING   → actively executing
    PAUSED    → suspended, can be resumed
    COMPLETED → finished successfully
    FAILED    → finished with unrecoverable errors
    CANCELLED → stopped by user or system

Events published (prefix "workflow."):
    workflow.started   → data: WorkflowState
    workflow.paused    → data: WorkflowState
    workflow.resumed   → data: WorkflowState
    workflow.completed → data: WorkflowResult
    workflow.failed    → data: WorkflowResult
    workflow.cancelled → data: WorkflowResult

Memory stored:
    - Full workflow history (goal, plan, status, reflection summary)
    - Execution statistics (cycles, tasks completed, time taken)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from brain.reflection import ReflectionAction
from config.settings import MAX_WORKFLOW_CYCLES
from models.enums import TaskStatus
from models.plan import Plan
from models.task import Task
from utils.logger import logger

if TYPE_CHECKING:
    from brain.planner import Planner
    from brain.reflection import ReflectionEngine
    from core.events import EventBus
    from core.executor import Executor
    from memory.memory_manager import MemoryManager


# ── Workflow state ────────────────────────────────────────────────────────────

class WorkflowStatus(str, Enum):
    CREATED   = "created"
    RUNNING   = "running"
    PAUSED    = "paused"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowState:
    """Live state of one workflow run."""
    workflow_id: str
    goal:        str
    status:      WorkflowStatus = WorkflowStatus.CREATED
    current_plan: Plan | None   = None
    cycle:        int           = 0
    started_at:   str | None    = None
    finished_at:  str | None    = None

    def __str__(self) -> str:
        return (
            f"Workflow[{self.workflow_id[:8]}] "
            f"'{self.goal[:50]}' — {self.status.value} "
            f"(cycle {self.cycle})"
        )


@dataclass
class WorkflowResult:
    """Final result of a completed (or failed/cancelled) workflow run."""
    workflow_id:    str
    goal:           str
    status:         WorkflowStatus
    plan:           Plan | None      = None
    cycles:         int              = 0
    reflection_summary: str          = ""
    total_time:     float            = 0.0
    error:          str | None       = None

    def succeeded(self) -> bool:
        return self.status == WorkflowStatus.COMPLETED

    def __str__(self) -> str:
        t = f"{self.total_time:.2f}s"
        return (
            f"WorkflowResult({self.status.value} | "
            f"'{self.goal[:50]}' | "
            f"cycles={self.cycles} | {t})"
        )


# ── Workflow Engine ───────────────────────────────────────────────────────────

class WorkflowEngine:
    """
    Orchestrates Planner → Executor → ReflectionEngine in a loop until
    the goal is achieved, unrecoverable, or cancelled.

    All dependencies are optional — the engine degrades gracefully.
    Without a Planner it falls back to a minimal two-task plan.
    Without a ReflectionEngine it skips reflection entirely.
    """

    def __init__(
        self,
        planner:          Planner         | None = None,
        executor:         Executor        | None = None,
        reflection:       ReflectionEngine | None = None,
        memory_manager:   MemoryManager   | None = None,
        event_bus:        EventBus        | None = None,
    ) -> None:
        self._planner    = planner
        self._executor   = executor
        self._reflection = reflection
        self._memory     = memory_manager
        self._events     = event_bus

        # Active workflow states keyed by workflow_id (supports future parallelism)
        self._states: dict[str, WorkflowState] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, goal: str) -> WorkflowResult:
        """
        Execute a complete goal from start to finish.

        Steps:
            1. Create a WorkflowState and publish workflow.started
            2. Ask the Planner for a Plan
            3. Execute the Plan via the Executor
            4. Reflect on the result
            5. Based on reflection: continue, retry, replan, or abort
            6. Repeat up to MAX_WORKFLOW_CYCLES
            7. Store history and publish final event

        Args:
            goal: Natural-language description of what IRIS should accomplish.

        Returns:
            WorkflowResult with final status, plan, and execution statistics.
        """
        state = self._create_state(goal)
        start = time.perf_counter()

        logger.info(f"Workflow started: '{goal[:80]}'")
        self._emit("workflow.started", state)

        reflection_summary = ""

        try:
            while state.cycle < MAX_WORKFLOW_CYCLES:

                # ── Check for pause or cancellation ──────────────────────────
                if state.status == WorkflowStatus.PAUSED:
                    logger.info(f"Workflow paused at cycle {state.cycle}.")
                    break
                if state.status == WorkflowStatus.CANCELLED:
                    logger.info("Workflow cancelled.")
                    break

                state.cycle += 1
                logger.info(f"Workflow cycle {state.cycle}/{MAX_WORKFLOW_CYCLES}")

                # ── Step 1: Plan ──────────────────────────────────────────────
                plan = self._plan(goal, state.current_plan)
                if plan is None:
                    return self._finish(
                        state, WorkflowStatus.FAILED, plan, start,
                        error="Planner unavailable and no existing plan to resume."
                    )
                state.current_plan = plan

                # ── Step 2: Execute ───────────────────────────────────────────
                state.status = WorkflowStatus.RUNNING
                plan = self._execute(plan)
                state.current_plan = plan

                # ── Step 3: Reflect ───────────────────────────────────────────
                outcome = self._reflect(plan)
                if outcome:
                    reflection_summary = outcome.summary

                # ── Step 4: Decide ────────────────────────────────────────────
                if plan.is_successful() or (
                    outcome and outcome.action == ReflectionAction.CONTINUE
                ):
                    logger.info("Workflow: goal achieved.")
                    return self._finish(
                        state, WorkflowStatus.COMPLETED, plan, start,
                        reflection_summary=reflection_summary,
                    )

                if outcome and outcome.action == ReflectionAction.ABORT:
                    return self._finish(
                        state, WorkflowStatus.FAILED, plan, start,
                        error=outcome.reason,
                        reflection_summary=reflection_summary,
                    )

                if outcome and outcome.action == ReflectionAction.RETRY:
                    logger.info(
                        f"Workflow: retrying {len(outcome.tasks_to_retry)} task(s)."
                    )
                    self._reset_tasks_for_retry(plan, outcome.tasks_to_retry)
                    # Loop again with the same plan (tasks reset to PENDING)
                    continue

                if outcome and outcome.action == ReflectionAction.REPLAN:
                    if outcome.new_plan:
                        logger.info("Workflow: switching to new plan from reflection.")
                        state.current_plan = outcome.new_plan
                    else:
                        logger.warning(
                            "Workflow: replan requested but no new plan generated. "
                            "Aborting."
                        )
                        return self._finish(
                            state, WorkflowStatus.FAILED, plan, start,
                            error="Re-planning failed — no new plan produced.",
                            reflection_summary=reflection_summary,
                        )
                    continue

                # No reflection engine — treat plan outcome as final
                if plan.is_successful():
                    return self._finish(
                        state, WorkflowStatus.COMPLETED, plan, start,
                        reflection_summary=reflection_summary,
                    )
                return self._finish(
                    state, WorkflowStatus.FAILED, plan, start,
                    reflection_summary=reflection_summary,
                )

            # Cycle limit exceeded
            if state.status not in (
                WorkflowStatus.PAUSED, WorkflowStatus.CANCELLED
            ):
                logger.error(
                    f"Workflow: exceeded max cycles ({MAX_WORKFLOW_CYCLES}). Aborting."
                )
                return self._finish(
                    state, WorkflowStatus.FAILED, state.current_plan, start,
                    error=f"Exceeded maximum workflow cycles ({MAX_WORKFLOW_CYCLES}).",
                    reflection_summary=reflection_summary,
                )

        except Exception as exc:
            logger.exception(f"Workflow: unexpected error: {exc}")
            return self._finish(
                state, WorkflowStatus.FAILED, state.current_plan, start,
                error=str(exc),
            )

        # Paused or cancelled — return current state as a partial result
        final_status = (
            WorkflowStatus.CANCELLED
            if state.status == WorkflowStatus.CANCELLED
            else WorkflowStatus.PAUSED
        )
        return self._finish(
            state, final_status, state.current_plan, start,
            reflection_summary=reflection_summary,
        )

    def resume(self, plan: Plan) -> WorkflowResult:
        """
        Resume execution from a saved/paused Plan.

        Finds any unfinished tasks, resets them to PENDING, and re-runs
        the full workflow loop starting from execute.

        Args:
            plan: A Plan that was previously paused or partially executed.

        Returns:
            WorkflowResult with the final outcome.
        """
        logger.info(f"Workflow: resuming plan '{plan.goal[:60]}'")

        # Reset unfinished tasks so the Executor picks them up
        for task in plan.tasks:
            if task.status in (TaskStatus.RUNNING, TaskStatus.WAITING):
                task.status = TaskStatus.PENDING
                task.started_at = None

        # Re-use the same goal but start a fresh workflow loop
        state = self._create_state(plan.goal)
        state.current_plan = plan
        self._emit("workflow.resumed", state)

        start = time.perf_counter()
        plan  = self._execute(plan)
        outcome = self._reflect(plan)

        if plan.is_successful() or (
            outcome and outcome.action == ReflectionAction.CONTINUE
        ):
            return self._finish(
                state, WorkflowStatus.COMPLETED, plan, start,
                reflection_summary=outcome.summary if outcome else "",
            )
        return self._finish(
            state, WorkflowStatus.FAILED, plan, start,
            error=outcome.reason if outcome else "Execution failed.",
            reflection_summary=outcome.summary if outcome else "",
        )

    def pause(self, workflow_id: str) -> bool:
        """
        Signal a running workflow to pause before its next cycle.

        Args:
            workflow_id: The ID returned by the WorkflowState.

        Returns:
            True if the workflow was found and paused, False otherwise.
        """
        state = self._states.get(workflow_id)
        if state and state.status == WorkflowStatus.RUNNING:
            state.status = WorkflowStatus.PAUSED
            self._emit("workflow.paused", state)
            logger.info(f"Workflow {workflow_id[:8]} paused.")
            return True
        return False

    def cancel(self, workflow_id: str) -> bool:
        """
        Signal a running or paused workflow to cancel immediately.

        Args:
            workflow_id: The ID returned by the WorkflowState.

        Returns:
            True if the workflow was found and cancelled, False otherwise.
        """
        state = self._states.get(workflow_id)
        if state and state.status in (
            WorkflowStatus.RUNNING, WorkflowStatus.PAUSED
        ):
            state.status = WorkflowStatus.CANCELLED
            self._emit("workflow.cancelled", state)
            logger.info(f"Workflow {workflow_id[:8]} cancelled.")
            return True
        return False

    def get_state(self, workflow_id: str) -> WorkflowState | None:
        """Return the current state of a workflow by ID."""
        return self._states.get(workflow_id)

    # ── Private — pipeline steps ──────────────────────────────────────────────

    def _plan(self, goal: str, existing_plan: Plan | None) -> Plan | None:
        """
        Get a Plan for the goal.
        If a current plan exists and has unfinished tasks, reuse it.
        Otherwise ask the Planner for a new one.
        """
        # Reuse existing plan if it has unfinished tasks
        if existing_plan and not existing_plan.is_finished():
            logger.debug("Workflow: reusing existing unfinished plan.")
            return existing_plan

        if self._planner is None:
            if existing_plan:
                return existing_plan
            logger.error("Workflow: no Planner available to create a plan.")
            return None

        return self._planner.create_plan(goal)

    def _execute(self, plan: Plan) -> Plan:
        """Run the plan through the Executor. No-op if Executor is absent."""
        if self._executor is None:
            logger.warning("Workflow: no Executor — skipping execution.")
            return plan
        return self._executor.execute_plan(plan)

    def _reflect(self, plan: Plan):
        """Reflect on the executed plan. Returns None if no engine available."""
        if self._reflection is None:
            return None
        return self._reflection.reflect(plan)

    # ── Private — state management ────────────────────────────────────────────

    def _create_state(self, goal: str) -> WorkflowState:
        """Build a fresh WorkflowState and register it."""
        wid   = str(uuid.uuid4())
        state = WorkflowState(
            workflow_id = wid,
            goal        = goal,
            status      = WorkflowStatus.CREATED,
            started_at  = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._states[wid] = state
        return state

    def _finish(
        self,
        state:              WorkflowState,
        status:             WorkflowStatus,
        plan:               Plan | None,
        start_time:         float,
        error:              str | None = None,
        reflection_summary: str        = "",
    ) -> WorkflowResult:
        """Finalise a workflow run, store history, publish event, return result."""
        elapsed             = round(time.perf_counter() - start_time, 3)
        state.status        = status
        state.finished_at   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state.current_plan  = plan

        result = WorkflowResult(
            workflow_id        = state.workflow_id,
            goal               = state.goal,
            status             = status,
            plan               = plan,
            cycles             = state.cycle,
            reflection_summary = reflection_summary,
            total_time         = elapsed,
            error              = error,
        )

        # Log
        icon = "✓" if result.succeeded() else "✗"
        logger.info(
            f"{icon} Workflow {state.workflow_id[:8]}: {status.value} | "
            f"'{state.goal[:50]}' | {elapsed:.2f}s | {state.cycle} cycle(s)"
        )
        if error:
            logger.error(f"  Error: {error}")

        # Store to memory
        self._store_history(result)

        # Publish final event
        event = f"workflow.{status.value}"
        self._emit(event, result)

        # Cleanup state after terminal finish
        if status in (
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        ):
            self._states.pop(state.workflow_id, None)

        return result

    @staticmethod
    def _reset_tasks_for_retry(plan: Plan, tasks: list[Task]) -> None:
        """
        Reset the given failed tasks back to PENDING so the Executor
        picks them up in the next cycle. Also resets their result/error fields.
        """
        for task in tasks:
            task.status      = TaskStatus.PENDING
            task.task_result = None
            task.started_at  = None
            task.finished_at = None
            logger.debug(f"Workflow: reset task [{task.id}] to PENDING for retry.")
        plan.update_status()

    # ── Private — memory integration ──────────────────────────────────────────

    def _store_history(self, result: WorkflowResult) -> None:
        """Save a workflow execution summary to memory."""
        if self._memory is None:
            return
        try:
            p = result.plan.progress() if result.plan else {}
            entry = (
                f"[WORKFLOW] Goal: '{result.goal[:80]}' | "
                f"Status: {result.status.value} | "
                f"Cycles: {result.cycles} | "
                f"Time: {result.total_time:.2f}s | "
                f"Tasks: {p.get('completed', '?')}/{p.get('total', '?')} done"
            )
            if result.error:
                entry += f" | Error: {result.error[:100]}"
            if result.reflection_summary:
                entry += f" | Reflection: {result.reflection_summary[:100]}"

            self._memory.store_memory(entry)
            logger.debug("Workflow: history stored.")
        except Exception as e:
            logger.warning(f"Workflow: could not store history: {e}")

    # ── Private — event bus ───────────────────────────────────────────────────

    def _emit(self, event_name: str, data: object = None) -> None:
        """Publish an event. Silently skips if no EventBus is wired."""
        if self._events is None:
            return
        try:
            self._events.emit(event_name, data)
        except Exception as e:
            logger.warning(f"Workflow: event '{event_name}' emit failed: {e}")
