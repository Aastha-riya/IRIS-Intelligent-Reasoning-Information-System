"""
models package

Public surface for shared data models used across brain, core, and tools.

Import from here — never import directly from models.enums, models.task,
models.plan, or models.result in application code:

    from models import Plan, Task, TaskResult, TaskStatus, TaskPriority   ✓
    from models.result import TaskResult                                   ✗
"""

from models.enums  import TaskPriority, TaskStatus
from models.plan   import Plan
from models.result import TaskResult
from models.task   import Task

__all__ = [
    "TaskStatus",
    "TaskPriority",
    "Task",
    "Plan",
    "TaskResult",
]
