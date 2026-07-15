"""
models/task.py

The Task data model — a single unit of work in a plan.

Every step in every plan is a Task. The Planner creates them,
the Workflow executes them, the ProgressTracker monitors them.

Status lifecycle:
    pending → running → completed
                     ↘ failed → (retry) → completed
                                        ↘ skipped
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """All valid states a task can be in."""
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    SKIPPED   = "skipped"


@dataclass
class Task:
    """
    A single unit of work inside a Plan.

    Attributes:
        id:           Unique integer identifier within the plan.
        description:  Human-readable description of what this task does.
        tool:         Name of the tool to invoke (must match ToolManager keys),
                      or "llm" to call the LLM directly, or None for reasoning steps.
        status:       Current lifecycle status (see TaskStatus).
        dependencies: IDs of tasks that must complete before this one runs.
        result:       Output produced by executing this task (populated at runtime).
        error:        Error message if the task failed (populated at runtime).
        retries:      Number of retry attempts made so far.
    """
    id:           int
    description:  str
    tool:         str | None       = None
    status:       TaskStatus       = TaskStatus.PENDING
    dependencies: list[int]        = field(default_factory=list)
    result:       str | None       = None
    error:        str | None       = None
    retries:      int              = 0

    def is_done(self) -> bool:
        """Return True if the task has reached a terminal state."""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
        )

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING

    def mark_completed(self, result: str = "") -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result

    def mark_failed(self, error: str = "") -> None:
        self.status = TaskStatus.FAILED
        self.error  = error

    def mark_skipped(self) -> None:
        self.status = TaskStatus.SKIPPED

    def to_dict(self) -> dict:
        """Serialise to a plain dict (for logging and storage)."""
        return {
            "id":           self.id,
            "description":  self.description,
            "tool":         self.tool,
            "status":       self.status.value,
            "dependencies": self.dependencies,
            "result":       self.result,
            "error":        self.error,
            "retries":      self.retries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Deserialise from a plain dict (e.g. from LLM JSON output)."""
        return cls(
            id           = int(data["id"]),
            description  = str(data["description"]),
            tool         = data.get("tool"),
            status       = TaskStatus(data.get("status", TaskStatus.PENDING)),
            dependencies = [int(d) for d in data.get("dependencies", [])],
            result       = data.get("result"),
            error        = data.get("error"),
            retries      = int(data.get("retries", 0)),
        )
