"""
models/plan.py

The Plan data model — a goal decomposed into an ordered list of Tasks.

Created by: Planner
Validated by: Validator
Executed by: Workflow
Tracked by: ProgressTracker
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.task import Task, TaskStatus


@dataclass
class Plan:
    """
    A complete execution plan for a user goal.

    Attributes:
        goal:       The original user request this plan addresses.
        tasks:      Ordered list of Task objects to execute.
        created_at: ISO timestamp when the plan was generated.
    """
    goal:       str
    tasks:      list[Task]  = field(default_factory=list)
    created_at: str         = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_task(self, task_id: int) -> Task | None:
        """Return the task with the given id, or None."""
        return next((t for t in self.tasks if t.id == task_id), None)

    def pending_tasks(self) -> list[Task]:
        """Return all tasks still waiting to run."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def completed_tasks(self) -> list[Task]:
        """Return all successfully completed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    def failed_tasks(self) -> list[Task]:
        """Return all tasks that ended in failure."""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    def is_complete(self) -> bool:
        """Return True when every task has reached a terminal state."""
        return all(t.is_done() for t in self.tasks)

    def is_successful(self) -> bool:
        """Return True when all tasks completed without failure."""
        return self.is_complete() and not self.failed_tasks()

    def summary(self) -> str:
        """Return a concise human-readable status summary."""
        total     = len(self.tasks)
        completed = len(self.completed_tasks())
        failed    = len(self.failed_tasks())
        pending   = len(self.pending_tasks())
        return (
            f"Plan: '{self.goal[:60]}' | "
            f"{completed}/{total} done | "
            f"{failed} failed | "
            f"{pending} pending"
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "goal":       self.goal,
            "created_at": self.created_at,
            "tasks":      [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        return cls(
            goal       = str(data["goal"]),
            tasks      = [Task.from_dict(t) for t in data.get("tasks", [])],
            created_at = data.get("created_at", ""),
        )
