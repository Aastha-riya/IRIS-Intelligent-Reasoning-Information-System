"""
models/enums.py

Shared enumerations for the IRIS models layer.

All status values and priority levels used across Planner, Workflow,
Executor, and ProgressTracker are defined here — once, in one place.

Why enums?
    Writing task.status = "running" lets typos like "Running" silently
    corrupt state. Enums make invalid values a hard error at assignment time:

        task.status = TaskStatus.RUNNING   # ✓ safe
        task.status = "Running"            # caught immediately by type checkers

──────────────────────────────────────────────────────────────────────────────
TaskStatus — string-valued (str, Enum)
──────────────────────────────────────────────────────────────────────────────

Full lifecycle:

    PENDING
       │
       ▼
    WAITING   ← blocked on unfinished dependencies
       │
       ▼
    RUNNING
       │
    ┌──┴──────────────┐
    ▼                 ▼
COMPLETED           FAILED
                      │
               ┌──────┴──────┐
               ▼             ▼
           (retry →)      SKIPPED   ← dependency failed, can't run
         COMPLETED        CANCELLED ← explicitly cancelled by user or agent

String values are used so TaskStatus serialises cleanly to JSON and
reads naturally in log files ("pending", "completed", not "1", "3").

──────────────────────────────────────────────────────────────────────────────
TaskPriority — integer-valued (IntEnum)
──────────────────────────────────────────────────────────────────────────────

    LOW = 1  <  NORMAL = 2  <  HIGH = 3  <  CRITICAL = 4

Integer values allow direct comparison and sorting:

    if task.priority >= TaskPriority.HIGH:
        run_immediately(task)

    tasks.sort(key=lambda t: t.priority, reverse=True)  # highest first
"""

from enum import Enum, IntEnum


class TaskStatus(str, Enum):
    """
    Lifecycle states of a single Task.

    String-valued so status serialises to readable JSON:
        {"status": "pending"}  not  {"status": 0}
    """

    PENDING   = "pending"    # Created, not yet eligible to run
    WAITING   = "waiting"    # Eligible but blocked on unfinished dependencies
    RUNNING   = "running"    # Currently being executed
    COMPLETED = "completed"  # Finished successfully
    FAILED    = "failed"     # Execution raised an error
    SKIPPED   = "skipped"    # Could not run because a dependency failed
    CANCELLED = "cancelled"  # Explicitly stopped before execution

    def is_terminal(self) -> bool:
        """Return True if no further state transitions are possible."""
        return self in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
            TaskStatus.CANCELLED,
        )

    def is_active(self) -> bool:
        """Return True if the task is currently doing work."""
        return self == TaskStatus.RUNNING

    def is_blocked(self) -> bool:
        """Return True if the task is waiting on another task."""
        return self == TaskStatus.WAITING


class TaskPriority(IntEnum):
    """
    Execution priority for a Task.

    Integer-valued so priorities can be compared and sorted numerically:
        TaskPriority.CRITICAL > TaskPriority.HIGH  →  True
        sorted(tasks, key=lambda t: t.priority, reverse=True)
    """

    LOW      = 1   # Background / informational tasks
    NORMAL   = 2   # Default priority
    HIGH     = 3   # Important, run before NORMAL tasks
    CRITICAL = 4   # Must run immediately; failure should halt the plan
