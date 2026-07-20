"""
models/task.py

The Task data model — a single unit of work in a Plan.

Every step in every plan is a Task.
    Planner         → creates Tasks
    Workflow        → executes Tasks, calls mark_* methods
    ProgressTracker → reads status, timestamps, result
    PlanValidator   → checks Tasks before execution
    Reflection      → inspects task_result to decide retry / skip

All enum values come from models.enums.
All execution output is wrapped in models.result.TaskResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from models.enums import TaskPriority, TaskStatus

if TYPE_CHECKING:
    # Avoid circular import at runtime — Task and TaskResult don't circularly
    # depend, but keeping the import in TYPE_CHECKING keeps startup clean.
    from models.result import TaskResult


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Task:
    """
    A single unit of work inside a Plan.

    Lifecycle timestamps:
        created_at  — set when the Task object is constructed
        started_at  — set when mark_running() is called
        finished_at — set when any terminal mark_* is called

    Result:
        task_result — a TaskResult object (set on completion or failure).
                      Replaces the old raw `result: str` field.
                      Access the output via task.task_result.output
                      or the text form via task.task_result.to_str().

    Attributes:
        id:           Unique integer identifier within the plan.
        description:  Human-readable description of what this task does.
        tool:         Tool name to invoke (must match ToolManager keys),
                      "llm" to call the LLM directly, or None for reasoning steps.
        status:       Current lifecycle state (TaskStatus enum).
        priority:     Execution priority (TaskPriority enum).
        dependencies: IDs of tasks that must reach COMPLETED before this runs.
        task_result:  TaskResult produced at runtime (None until terminal state).
        retries:      Number of retry attempts made so far.
        created_at:   When this Task was created.
        started_at:   When execution began (None until mark_running()).
        finished_at:  When execution ended (None until terminal state).
    """

    # ── Required fields ───────────────────────────────────────────────────────
    id:           int
    description:  str

    # ── Optional fields with defaults ─────────────────────────────────────────
    tool:         str | None    = None
    status:       TaskStatus    = TaskStatus.PENDING
    priority:     TaskPriority  = TaskPriority.NORMAL
    dependencies: list[int]     = field(default_factory=list)
    task_result:  TaskResult | None = field(default=None)   # type: ignore[type-arg]
    retries:      int           = 0

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at:   str           = field(default_factory=_now)
    started_at:   str | None    = None
    finished_at:  str | None    = None

    # ── State queries ─────────────────────────────────────────────────────────

    def is_done(self) -> bool:
        """Return True if the task has reached any terminal state."""
        return self.status.is_terminal()

    def is_ready(self, completed_ids: set[int]) -> bool:
        """
        Return True if all dependencies have completed and the task
        is in a runnable state (PENDING or WAITING).

        Args:
            completed_ids: Set of task IDs that have reached COMPLETED.
        """
        if self.status not in (TaskStatus.PENDING, TaskStatus.WAITING):
            return False
        return all(dep in completed_ids for dep in self.dependencies)

    def duration(self) -> float | None:
        """
        Return execution duration in seconds, or None if not yet finished.
        Derived from started_at and finished_at timestamps.
        """
        if not self.started_at or not self.finished_at:
            return None
        fmt = "%Y-%m-%d %H:%M:%S"
        try:
            start = datetime.strptime(self.started_at,  fmt)
            end   = datetime.strptime(self.finished_at, fmt)
            return (end - start).total_seconds()
        except ValueError:
            return None

    # ── State transitions ─────────────────────────────────────────────────────

    def mark_waiting(self) -> None:
        """Transition to WAITING — eligible but blocked on unfinished dependencies."""
        self.status = TaskStatus.WAITING

    def mark_running(self) -> None:
        """Transition to RUNNING — record start timestamp."""
        self.status     = TaskStatus.RUNNING
        self.started_at = _now()

    def mark_completed(self, result: TaskResult) -> None:
        """
        Transition to COMPLETED — store the TaskResult and record finish time.

        Args:
            result: The TaskResult produced by the tool execution.
        """
        self.status      = TaskStatus.COMPLETED
        self.task_result = result
        self.finished_at = _now()

    def mark_failed(self, result: TaskResult) -> None:
        """
        Transition to FAILED — store the TaskResult (which holds the error)
        and record finish time.

        Args:
            result: A failure TaskResult (result.success == False).
        """
        self.status      = TaskStatus.FAILED
        self.task_result = result
        self.finished_at = _now()

    def mark_skipped(self) -> None:
        """Transition to SKIPPED — a required dependency failed or was cancelled."""
        self.status      = TaskStatus.SKIPPED
        self.finished_at = _now()

    def mark_cancelled(self) -> None:
        """Transition to CANCELLED — explicitly stopped before execution."""
        self.status      = TaskStatus.CANCELLED
        self.finished_at = _now()

    # ── Convenience accessors ─────────────────────────────────────────────────

    @property
    def output(self) -> object:
        """Shortcut to task_result.output, or None if no result yet."""
        return self.task_result.output if self.task_result else None

    @property
    def error(self) -> str | None:
        """Shortcut to task_result.error, or None if no result yet."""
        return self.task_result.error if self.task_result else None

    @property
    def output_text(self) -> str:
        """Shortcut to task_result.to_str() — always returns a string."""
        return self.task_result.to_str() if self.task_result else ""

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "id":           self.id,
            "description":  self.description,
            "tool":         self.tool,
            "status":       self.status.value,
            "priority":     self.priority.value,
            "dependencies": self.dependencies,
            "task_result":  self.task_result.to_dict() if self.task_result else None,
            "retries":      self.retries,
            "created_at":   self.created_at,
            "started_at":   self.started_at,
            "finished_at":  self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Deserialise from a plain dict (e.g. from LLM JSON output or storage)."""
        from models.result import TaskResult   # local import breaks circular dependency

        raw_result = data.get("task_result")

        return cls(
            id          = int(data["id"]),
            description = str(data["description"]),
            tool        = data.get("tool"),
            status      = TaskStatus(data.get("status", TaskStatus.PENDING.value)),
            priority    = TaskPriority(int(data.get("priority", TaskPriority.NORMAL.value))),
            dependencies = [int(d) for d in data.get("dependencies", [])],
            task_result = TaskResult.from_dict(raw_result) if raw_result else None,
            retries     = int(data.get("retries", 0)),
            created_at  = data.get("created_at", _now()),
            started_at  = data.get("started_at"),
            finished_at = data.get("finished_at"),
        )
