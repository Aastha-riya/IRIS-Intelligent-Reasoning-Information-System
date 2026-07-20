"""
core/progress_tracker.py

Tracks and reports task status across a Plan execution.

Single responsibility:
    Plan  →  real-time status display and progress queries

No execution logic. No tool calls. No LLM.
Just monitoring, querying, and reporting.

Used by Workflow to announce what step it is on.
Used by IrisAssistant to answer "What are you doing?" queries.
"""

from __future__ import annotations

from models.enums import TaskStatus
from models.plan  import Plan
from models.task  import Task
from utils.logger import logger


class ProgressTracker:
    """
    Tracks task execution progress for a single Plan.

    Attach one ProgressTracker per Plan run. The Workflow calls
    update() after each task state change.
    """

    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    # ── Workflow-facing API ───────────────────────────────────────────────────

    def on_task_start(self, task: Task) -> None:
        """Called by Workflow when a task begins running."""
        logger.info(
            f"[{self._position(task)}] Running: {task.description}"
            + (f" (tool: {task.tool})" if task.tool else "")
        )

    def on_task_complete(self, task: Task) -> None:
        """Called by Workflow when a task completes successfully."""
        logger.info(
            f"[{self._position(task)}] ✓ Completed: {task.description}"
        )

    def on_task_failed(self, task: Task) -> None:
        """Called by Workflow when a task fails."""
        logger.warning(
            f"[{self._position(task)}] ✗ Failed: {task.description} — {task.error}"
        )

    def on_task_skipped(self, task: Task) -> None:
        """Called by Workflow when a task is skipped due to a failed dependency."""
        logger.warning(
            f"[{self._position(task)}] ⟳ Skipped: {task.description}"
        )

    def on_plan_complete(self) -> None:
        """Called by Workflow when the full plan finishes."""
        logger.info(f"Plan complete — {self._plan.summary()}")

    # ── Query API ─────────────────────────────────────────────────────────────

    def current_step(self) -> str:
        """Return a human-readable description of the currently running task."""
        running = [t for t in self._plan.tasks if t.status == TaskStatus.RUNNING]
        if not running:
            return "No task is currently running."
        return f"Currently on step {running[0].id}: {running[0].description}"

    def progress_report(self) -> str:
        """Return a full progress summary of all tasks in the plan."""
        lines = [f"Goal: {self._plan.goal}", ""]
        for task in self._plan.tasks:
            icon = {
                TaskStatus.PENDING:   "○",
                TaskStatus.WAITING:   "◔",
                TaskStatus.RUNNING:   "▶",
                TaskStatus.COMPLETED: "✓",
                TaskStatus.FAILED:    "✗",
                TaskStatus.SKIPPED:   "⟳",
                TaskStatus.CANCELLED: "⊘",
            }.get(task.status, "?")
            lines.append(f"  {icon} [{task.id}] {task.description}  ({task.status.value})")
            if task.error:
                lines.append(f"       Error: {task.error}")
        lines.append("")
        lines.append(self._plan.summary())
        return "\n".join(lines)

    def percent_complete(self) -> float:
        """Return completion percentage (0.0 – 100.0)."""
        total = len(self._plan.tasks)
        if total == 0:
            return 100.0
        done  = sum(1 for t in self._plan.tasks if t.is_done())
        return round(done / total * 100, 1)

    # ── Private ───────────────────────────────────────────────────────────────

    def _position(self, task: Task) -> str:
        """Return 'n/total' position string for a task."""
        total = len(self._plan.tasks)
        return f"{task.id}/{total}"
