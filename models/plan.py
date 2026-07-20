"""
models/plan.py

The Plan data model — a user goal decomposed into an ordered list of Tasks.

Created by:   Planner
Validated by: PlanValidator
Executed by:  Workflow
Tracked by:   ProgressTracker

A Plan is the contract between the Planner (which builds it) and the
Workflow (which runs it). Neither side needs to know the other's internals
as long as they agree on this shared model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.enums import TaskPriority, TaskStatus
from models.task  import Task


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Plan:
    """
    A complete execution plan for a user goal.

    Attributes:
        goal:       The original user request this plan addresses.
        tasks:      Ordered list of Task objects to execute.
        status:     Overall plan status — mirrors the worst task status:
                        "pending"   → no tasks have started
                        "running"   → at least one task is running
                        "completed" → all tasks finished successfully
                        "failed"    → one or more tasks failed
                        "cancelled" → plan was explicitly cancelled
        metadata:   Arbitrary key-value pairs for extensions
                    (e.g. {"source": "user", "model": "llama3.2"}).
        created_at: ISO timestamp when the plan was generated.
    """

    goal:       str
    tasks:      list[Task] = field(default_factory=list)
    status:     str        = "pending"
    metadata:   dict       = field(default_factory=dict)
    created_at: str        = field(default_factory=_now)

    # ── Task management ───────────────────────────────────────────────────────

    def add_task(self, task: Task) -> None:
        """
        Append a task to the plan.
        Raises ValueError if a task with the same ID already exists.
        """
        if self.get_task(task.id) is not None:
            raise ValueError(
                f"Plan already contains a task with id={task.id}. "
                f"All task IDs must be unique."
            )
        self.tasks.append(task)

    def remove_task(self, task_id: int) -> bool:
        """
        Remove the task with the given ID from the plan.

        Returns:
            True if a task was removed, False if no matching task was found.
        """
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        return len(self.tasks) < original_len

    def get_task(self, task_id: int) -> Task | None:
        """Return the task with the given id, or None if not found."""
        return next((t for t in self.tasks if t.id == task_id), None)

    # ── Task filter queries ───────────────────────────────────────────────────

    def pending_tasks(self) -> list[Task]:
        """Tasks created but not yet eligible to run."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def waiting_tasks(self) -> list[Task]:
        """Tasks eligible but blocked on unfinished dependencies."""
        return [t for t in self.tasks if t.status == TaskStatus.WAITING]

    def running_tasks(self) -> list[Task]:
        """Tasks currently being executed."""
        return [t for t in self.tasks if t.status == TaskStatus.RUNNING]

    def completed_tasks(self) -> list[Task]:
        """Tasks that finished successfully."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    def failed_tasks(self) -> list[Task]:
        """Tasks that ended in an error."""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    def skipped_tasks(self) -> list[Task]:
        """Tasks skipped because a dependency failed."""
        return [t for t in self.tasks if t.status == TaskStatus.SKIPPED]

    def cancelled_tasks(self) -> list[Task]:
        """Tasks explicitly cancelled."""
        return [t for t in self.tasks if t.status == TaskStatus.CANCELLED]

    def completed_ids(self) -> set[int]:
        """Return the set of IDs for all successfully completed tasks."""
        return {t.id for t in self.completed_tasks()}

    # ── Scheduling ────────────────────────────────────────────────────────────

    def next_ready_tasks(self) -> list[Task]:
        """
        Return all tasks that are ready to execute right now.

        A task is ready when:
          - Its status is PENDING or WAITING, AND
          - All its dependency IDs are in the completed set.

        Results are sorted by priority descending (CRITICAL first).

        The Workflow calls this each iteration to find what to run next.
        """
        done_ids = self.completed_ids()
        ready = [t for t in self.tasks if t.is_ready(done_ids)]
        return sorted(ready, key=lambda t: t.priority, reverse=True)

    # ── Progress reporting ────────────────────────────────────────────────────

    def progress(self) -> dict:
        """
        Return a structured progress snapshot.

        Returns:
            {
                "total":      int,   # total task count
                "completed":  int,
                "running":    int,
                "pending":    int,   # PENDING + WAITING combined
                "failed":     int,
                "skipped":    int,
                "cancelled":  int,
                "percent":    float  # 0.0 – 100.0
            }
        """
        total     = len(self.tasks)
        completed = len(self.completed_tasks())
        pending   = len(self.pending_tasks()) + len(self.waiting_tasks())

        return {
            "total":     total,
            "completed": completed,
            "running":   len(self.running_tasks()),
            "pending":   pending,
            "failed":    len(self.failed_tasks()),
            "skipped":   len(self.skipped_tasks()),
            "cancelled": len(self.cancelled_tasks()),
            "percent":   round(completed / total * 100, 1) if total else 100.0,
        }

    # ── Plan-level queries ────────────────────────────────────────────────────

    def is_finished(self) -> bool:
        """
        True when every task has reached a terminal state.
        (Replaces the former is_complete() — name chosen to avoid confusion
        with completed_tasks() which filters only COMPLETED status.)
        """
        return bool(self.tasks) and all(t.is_done() for t in self.tasks)

    def is_successful(self) -> bool:
        """True when the plan is finished and no task failed or was cancelled."""
        return (
            self.is_finished()
            and not self.failed_tasks()
            and not self.cancelled_tasks()
        )

    def update_status(self) -> None:
        """
        Recompute and update self.status to reflect the current task states.
        Call this after any task state transition.

        Precedence:
            any FAILED     → "failed"
            any CANCELLED  → "cancelled"
            any RUNNING    → "running"
            all terminal   → "completed"
            otherwise      → "pending"
        """
        if self.failed_tasks():
            self.status = "failed"
        elif self.cancelled_tasks():
            self.status = "cancelled"
        elif self.running_tasks():
            self.status = "running"
        elif self.is_finished():
            self.status = "completed"
        else:
            self.status = "pending"

    def summary(self) -> str:
        """Return a concise human-readable status line."""
        p = self.progress()
        return (
            f"Plan: '{self.goal[:60]}' | "
            f"{p['completed']}/{p['total']} done "
            f"({p['percent']}%) | "
            f"{p['failed']} failed | "
            f"{p['pending']} pending"
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "goal":       self.goal,
            "status":     self.status,
            "metadata":   self.metadata,
            "created_at": self.created_at,
            "tasks":      [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        """Deserialise from a plain dict."""
        return cls(
            goal       = str(data["goal"]),
            tasks      = [Task.from_dict(t) for t in data.get("tasks", [])],
            status     = data.get("status", "pending"),
            metadata   = dict(data.get("metadata", {})),
            created_at = data.get("created_at", _now()),
        )
