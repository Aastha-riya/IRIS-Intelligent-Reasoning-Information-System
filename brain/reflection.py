"""
brain/reflection.py

The Reflection Engine — evaluates plan execution and decides what to do next.

Single responsibility:
    Completed/failed Plan  →  ReflectionOutcome (continue | retry | replan | abort)

The Reflection Engine does NOT execute tasks. It only evaluates results and
decides the next action. Execution is always delegated back to the Executor.

Decision tree per plan:
    Plan finished successfully?
        └── Yes → CONTINUE (nothing to do)
    Any failed tasks?
        └── Individual task retry limit not yet reached?
                └── Yes → RETRY those tasks
        └── Failed task count ≥ REFLECTION_FAIL_THRESHOLD?
                └── Re-plan attempts remaining?
                        └── Yes  → REPLAN (send goal back to Planner)
                        └── No   → ABORT
        └── Else → CONTINUE (tolerate minor failures)

Error classification:
    Transient  — network, timeout, resource temporarily unavailable → retry
    Permanent  — file not found, unknown tool, bad input          → skip/replan
    Unknown    — everything else                                   → retry once

Learning (via MemoryManager):
    - Every failure is stored as a memory for future context
    - Successful strategies are stored as positive examples
    - A reflection summary is stored after each plan completes

Events published:
    "reflection.started"   → data: plan
    "reflection.retry"     → data: {"task": task, "reason": str}
    "reflection.replan"    → data: {"plan": plan, "reason": str}
    "reflection.abort"     → data: {"plan": plan, "reason": str}
    "reflection.completed" → data: ReflectionOutcome
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import ollama

from config.settings import (
    DEFAULT_MODEL,
    MAX_REPLAN_ATTEMPTS,
    MAX_TASK_RETRIES,
    REFLECTION_FAIL_THRESHOLD,
)
from models.enums import TaskStatus
from models.plan import Plan
from models.task import Task
from utils.logger import logger

if TYPE_CHECKING:
    from brain.planner import Planner
    from core.events import EventBus
    from core.executor import Executor
    from memory.memory_manager import MemoryManager


# ── Error categories ──────────────────────────────────────────────────────────

class ErrorCategory(str, Enum):
    TRANSIENT = "transient"   # Retry is likely to succeed
    PERMANENT = "permanent"   # Retrying won't help — skip or replan
    UNKNOWN   = "unknown"     # Retry once, then treat as permanent


# Keywords that signal each category (case-insensitive)
_TRANSIENT_KEYWORDS = ("timeout", "connection", "network", "unavailable",
                       "rate limit", "temporary", "retry")
_PERMANENT_KEYWORDS = ("not found", "unknown tool", "invalid", "permission",
                       "does not exist", "unsupported", "no such file")


def _classify_error(error: str | None) -> ErrorCategory:
    """Categorise a task error message into transient, permanent, or unknown."""
    if not error:
        return ErrorCategory.UNKNOWN
    lowered = error.lower()
    if any(kw in lowered for kw in _TRANSIENT_KEYWORDS):
        return ErrorCategory.TRANSIENT
    if any(kw in lowered for kw in _PERMANENT_KEYWORDS):
        return ErrorCategory.PERMANENT
    return ErrorCategory.UNKNOWN


# ── Reflection outcome ────────────────────────────────────────────────────────

class ReflectionAction(str, Enum):
    CONTINUE = "continue"   # Plan succeeded or failures are tolerable
    RETRY    = "retry"      # Re-run specific failed tasks
    REPLAN   = "replan"     # Abandon this plan, generate a new one
    ABORT    = "abort"      # Give up — too many failures, no retries left


@dataclass
class ReflectionOutcome:
    """
    Result of a reflection pass over a completed plan.

    Attributes:
        action:         What the engine recommends doing next.
        tasks_to_retry: Failed tasks that should be re-executed.
        new_plan:       Replacement plan (populated when action == REPLAN).
        reason:         Human-readable explanation of the decision.
        summary:        Full reflection narrative (may include LLM analysis).
    """
    action:         ReflectionAction
    tasks_to_retry: list[Task]  = field(default_factory=list)
    new_plan:       Plan | None = None
    reason:         str         = ""
    summary:        str         = ""

    def __str__(self) -> str:
        return (
            f"ReflectionOutcome(action={self.action.value}, "
            f"retries={len(self.tasks_to_retry)}, "
            f"reason='{self.reason[:80]}')"
        )


# ── Reflection Engine ─────────────────────────────────────────────────────────

class ReflectionEngine:
    """
    Evaluates plan execution results and decides the next action.

    All dependencies are optional — the engine degrades gracefully without
    Planner (no re-planning), MemoryManager (no learning), or EventBus
    (no events), and LLM (rule-based reflection only).
    """

    def __init__(
        self,
        planner:        Planner        | None = None,
        executor:       Executor       | None = None,
        memory_manager: MemoryManager  | None = None,
        event_bus:      EventBus       | None = None,
        use_llm:        bool           = False,
    ) -> None:
        """
        Args:
            planner:        Planner instance for re-planning.
            executor:       Executor instance for re-running tasks.
            memory_manager: MemoryManager for storing reflection learnings.
            event_bus:      EventBus for publishing reflection events.
            use_llm:        If True, ask the LLM to explain failures and suggest
                            improvements (optional, adds latency).
        """
        self._planner  = planner
        self._executor = executor
        self._memory   = memory_manager
        self._events   = event_bus
        self._use_llm  = use_llm

        # Track how many times re-planning has been attempted per goal
        self._replan_counts: dict[str, int] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def reflect(self, plan: Plan) -> ReflectionOutcome:
        """
        Evaluate the completed plan and return a ReflectionOutcome.

        This is the main entry point. Call it after Executor.execute_plan().

        Args:
            plan: A Plan whose all tasks have reached terminal states.

        Returns:
            ReflectionOutcome describing what to do next.
        """
        logger.info(f"Reflection started for plan: '{plan.goal[:60]}'")
        self._emit("reflection.started", plan)

        # Plan succeeded — nothing to reflect on
        if plan.is_successful():
            outcome = self._outcome_continue(plan)
            self._store_success(plan)
            self._emit("reflection.completed", outcome)
            logger.info(f"Reflection: {outcome}")
            return outcome

        # Analyse failures
        failed_tasks    = plan.failed_tasks()
        retryable       = [t for t in failed_tasks if self.should_retry(t)]
        non_retryable   = [t for t in failed_tasks if not self.should_retry(t)]

        logger.info(
            f"Reflection: {len(failed_tasks)} failed tasks — "
            f"{len(retryable)} retryable, {len(non_retryable)} permanent."
        )

        # Store all failures in memory for future context
        for task in failed_tasks:
            self._store_failure(task)

        # ── Decision ──────────────────────────────────────────────────────────
        if retryable:
            outcome = self._outcome_retry(plan, retryable)

        elif self.should_replan(plan):
            outcome = self._outcome_replan(plan)

        else:
            outcome = self._outcome_abort(plan, failed_tasks)

        # Optional: ask LLM for deeper analysis
        if self._use_llm and failed_tasks:
            outcome.summary = self._llm_analysis(plan, failed_tasks)

        self._store_reflection_summary(plan, outcome)
        self._emit("reflection.completed", outcome)
        logger.info(f"Reflection: {outcome}")
        return outcome

    def reflect_task(self, task: Task) -> ReflectionAction:
        """
        Evaluate a single completed task and return the recommended action.

        Args:
            task: A Task in a terminal state (COMPLETED, FAILED, SKIPPED).

        Returns:
            CONTINUE if the task succeeded or was skipped expectedly.
            RETRY    if the task failed and retrying is appropriate.
            REPLAN   if the error is permanent and re-planning is needed.
        """
        if task.status == TaskStatus.COMPLETED:
            return ReflectionAction.CONTINUE

        if task.status == TaskStatus.SKIPPED:
            return ReflectionAction.CONTINUE   # dependency failed, not this task

        if task.status != TaskStatus.FAILED:
            return ReflectionAction.CONTINUE   # CANCELLED etc — no action

        if self.should_retry(task):
            return ReflectionAction.RETRY

        category = _classify_error(task.error)
        if category == ErrorCategory.PERMANENT:
            return ReflectionAction.REPLAN

        return ReflectionAction.RETRY

    def should_retry(self, task: Task) -> bool:
        """
        Return True if the task should be retried.

        A task should be retried when:
          - It is in FAILED state
          - It has not yet exhausted the retry limit
          - Its error is not classified as permanent
        """
        if task.status != TaskStatus.FAILED:
            return False
        if task.retries >= MAX_TASK_RETRIES:
            return False
        category = _classify_error(task.error)
        return category != ErrorCategory.PERMANENT

    def should_replan(self, plan: Plan) -> bool:
        """
        Return True if the plan should be abandoned and re-generated.

        Re-planning is triggered when:
          - More failed tasks than REFLECTION_FAIL_THRESHOLD
          - Re-plan attempts for this goal haven't exceeded MAX_REPLAN_ATTEMPTS
          - A Planner is available
        """
        if self._planner is None:
            return False

        failed_count = len(plan.failed_tasks())
        if failed_count < REFLECTION_FAIL_THRESHOLD:
            return False

        attempts = self._replan_counts.get(plan.goal, 0)
        return attempts < MAX_REPLAN_ATTEMPTS

    # ── Private — outcome builders ────────────────────────────────────────────

    def _outcome_continue(self, plan: Plan) -> ReflectionOutcome:
        reason = f"Plan '{plan.goal[:60]}' completed successfully."
        logger.info(f"Reflection: CONTINUE — {reason}")
        return ReflectionOutcome(
            action  = ReflectionAction.CONTINUE,
            reason  = reason,
            summary = reason,
        )

    def _outcome_retry(self, plan: Plan, retryable: list[Task]) -> ReflectionOutcome:
        ids    = [t.id for t in retryable]
        reason = f"Retrying {len(retryable)} failed task(s): {ids}"
        logger.info(f"Reflection: RETRY — {reason}")

        for task in retryable:
            self._emit("reflection.retry", {"task": task, "reason": reason})

        return ReflectionOutcome(
            action         = ReflectionAction.RETRY,
            tasks_to_retry = retryable,
            reason         = reason,
            summary        = reason,
        )

    def _outcome_replan(self, plan: Plan) -> ReflectionOutcome:
        self._replan_counts[plan.goal] = self._replan_counts.get(plan.goal, 0) + 1
        attempt = self._replan_counts[plan.goal]
        reason  = (
            f"Too many failures ({len(plan.failed_tasks())}). "
            f"Re-planning attempt {attempt}/{MAX_REPLAN_ATTEMPTS}."
        )
        logger.warning(f"Reflection: REPLAN — {reason}")
        self._emit("reflection.replan", {"plan": plan, "reason": reason})

        new_plan: Plan | None = None
        if self._planner:
            try:
                new_plan = self._planner.create_plan(plan.goal)
                logger.info(
                    f"Reflection: new plan generated — "
                    f"{len(new_plan.tasks)} tasks."
                )
            except Exception as e:
                logger.exception(f"Reflection: re-planning failed: {e}")

        return ReflectionOutcome(
            action   = ReflectionAction.REPLAN,
            new_plan = new_plan,
            reason   = reason,
            summary  = reason,
        )

    def _outcome_abort(self, plan: Plan, failed: list[Task]) -> ReflectionOutcome:
        ids    = [t.id for t in failed]
        reason = (
            f"Aborting: {len(failed)} permanent failure(s) in tasks {ids}. "
            f"No re-plan attempts remaining."
        )
        logger.error(f"Reflection: ABORT — {reason}")
        self._emit("reflection.abort", {"plan": plan, "reason": reason})

        return ReflectionOutcome(
            action  = ReflectionAction.ABORT,
            reason  = reason,
            summary = reason,
        )

    # ── Private — learning / memory ───────────────────────────────────────────

    def _store_failure(self, task: Task) -> None:
        """Record a task failure in memory for future context."""
        if self._memory is None:
            return
        try:
            entry = (
                f"[FAILURE] Task '{task.description}' "
                f"(tool={task.tool}) failed: {task.error}"
            )
            self._memory.store_memory(entry)
            logger.debug(f"Reflection: stored failure for task [{task.id}].")
        except Exception as e:
            logger.warning(f"Reflection: could not store failure: {e}")

    def _store_success(self, plan: Plan) -> None:
        """Record a successful plan execution as a positive example."""
        if self._memory is None:
            return
        try:
            tools_used = list({t.tool for t in plan.tasks if t.tool})
            entry = (
                f"[SUCCESS] Plan '{plan.goal[:80]}' completed. "
                f"Tasks: {len(plan.tasks)}. "
                f"Tools used: {tools_used}."
            )
            self._memory.store_memory(entry)
            logger.debug("Reflection: stored success record.")
        except Exception as e:
            logger.warning(f"Reflection: could not store success: {e}")

    def _store_reflection_summary(
        self,
        plan:    Plan,
        outcome: ReflectionOutcome,
    ) -> None:
        """Save a full reflection summary to memory."""
        if self._memory is None:
            return
        try:
            p       = plan.progress()
            summary = (
                f"[REFLECTION] Goal: '{plan.goal[:80]}' | "
                f"Action: {outcome.action.value} | "
                f"Completed: {p['completed']}/{p['total']} | "
                f"Failed: {p['failed']} | "
                f"Reason: {outcome.reason[:120]}"
            )
            self._memory.store_memory(summary)
            logger.debug("Reflection: stored reflection summary.")
        except Exception as e:
            logger.warning(f"Reflection: could not store summary: {e}")

    # ── Private — optional LLM analysis ──────────────────────────────────────

    def _llm_analysis(self, plan: Plan, failed_tasks: list[Task]) -> str:
        """
        Ask the LLM to explain the failures and suggest improvements.
        Returns the analysis as a string. Falls back to empty string on error.
        """
        failures = "\n".join(
            f"  - Task [{t.id}] '{t.description}': {t.error}"
            for t in failed_tasks
        )
        prompt = (
            f"You are an AI reflection engine. "
            f"The following plan failed:\n\n"
            f"Goal: {plan.goal}\n\n"
            f"Failed tasks:\n{failures}\n\n"
            f"Briefly explain why these tasks may have failed and "
            f"suggest how to improve the plan. Keep it under 150 words."
        )
        try:
            response = ollama.chat(
                model    = DEFAULT_MODEL,
                messages = [{"role": "user", "content": prompt}],
            )
            analysis: str = response["message"]["content"].strip()
            logger.info("Reflection: LLM analysis complete.")
            return analysis
        except Exception as e:
            logger.warning(f"Reflection: LLM analysis failed: {e}")
            return ""

    # ── Private — event bus ───────────────────────────────────────────────────

    def _emit(self, event_name: str, data: object = None) -> None:
        """Publish an event. Silently skips if no EventBus is wired."""
        if self._events is None:
            return
        try:
            self._events.emit(event_name, data)
        except Exception as e:
            logger.warning(f"Reflection: event '{event_name}' emit failed: {e}")
