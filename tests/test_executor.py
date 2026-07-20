"""
tests/test_executor.py

Unit tests for core/executor.py (Executor).

No LLM, no real ToolManager, no real MemoryManager required.
All tool calls are replaced with lightweight fakes.

Run with:
    python -m pytest tests/test_executor.py -v

Test cases:
    1.  Execute single task with a tool → COMPLETED, TaskResult stored.
    2.  Execute multi-task plan in sequence → all COMPLETED.
    3.  Dependency order respected — task 2 runs only after task 1.
    4.  Task with tool=None (reasoning step) → succeeds immediately.
    5.  Task with tool="llm" → succeeds as LLM pass-through.
    6.  Failed tool → task marked FAILED after max retries.
    7.  Failed task causes dependent task to be SKIPPED.
    8.  Empty plan → returned unchanged, no crash.
    9.  Unknown tool → task marked FAILED.
    10. Retry count increments on each failed attempt.
    11. Events published: plan.started, task.started, task.completed, plan.completed.
    12. Successful plan → plan.status == "completed".
    13. Failed plan → plan.status == "failed".
    14. execute_task() returns the final TaskResult.
    15. Execution time is recorded on the TaskResult.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.events import EventBus
from core.executor import Executor
from core.progress_tracker import ProgressTracker
from models.enums import TaskPriority, TaskStatus
from models.plan import Plan
from models.task import Task


# ── Helpers / fakes ───────────────────────────────────────────────────────────

class _FakeTool:
    """Minimal tool double — succeeds by returning its query string."""
    def execute(self, query: str) -> str:
        return f"result: {query}"


class _FailingTool:
    """Tool double that always raises an exception."""
    def execute(self, query: str) -> str:
        raise RuntimeError("Tool exploded")


def _make_tool_manager(tools: dict | None = None) -> MagicMock:
    """Return a fake ToolManager with the given tools dict."""
    tm = MagicMock()
    tm.tools = tools or {"calculator": _FakeTool(), "file_reader": _FakeTool()}
    return tm


def _make_plan(*tasks: Task, goal: str = "Test goal") -> Plan:
    return Plan(goal=goal, tasks=list(tasks))


def _task(
    task_id:      int,
    tool:         str | None = None,
    deps:         list[int] | None = None,
    priority:     TaskPriority = TaskPriority.NORMAL,
) -> Task:
    return Task(
        id           = task_id,
        description  = f"Task {task_id}",
        tool         = tool,
        priority     = priority,
        dependencies = deps or [],
    )


def _executor(tools: dict | None = None) -> Executor:
    return Executor(tool_manager=_make_tool_manager(tools))


# ── Test 1: Single task → COMPLETED ──────────────────────────────────────────

def test_single_task_completes() -> None:
    plan = _make_plan(_task(1, tool="calculator"))
    result_plan = _executor().execute_plan(plan)

    assert result_plan.tasks[0].status == TaskStatus.COMPLETED
    assert result_plan.tasks[0].task_result is not None
    assert result_plan.tasks[0].task_result.success is True


# ── Test 2: Multi-task plan → all COMPLETED ───────────────────────────────────

def test_multi_task_all_complete() -> None:
    plan = _make_plan(
        _task(1, tool="calculator"),
        _task(2, tool="file_reader", deps=[1]),
        _task(3, tool=None, deps=[2]),
    )
    _executor().execute_plan(plan)

    for task in plan.tasks:
        assert task.status == TaskStatus.COMPLETED, (
            f"Task {task.id} expected COMPLETED, got {task.status}"
        )


# ── Test 3: Dependency order respected ────────────────────────────────────────

def test_dependency_order_respected() -> None:
    """Task 2 must not start until task 1 has finished."""
    order: list[int] = []

    class _OrderTrackingTool:
        def __init__(self, tid: int):
            self._id = tid
        def execute(self, query: str) -> str:
            order.append(self._id)
            return f"done {self._id}"

    tm = MagicMock()
    tm.tools = {
        "tool_a": _OrderTrackingTool(1),
        "tool_b": _OrderTrackingTool(2),
    }
    executor = Executor(tool_manager=tm)
    plan = _make_plan(
        _task(1, tool="tool_a"),
        _task(2, tool="tool_b", deps=[1]),
    )
    executor.execute_plan(plan)

    assert order == [1, 2], f"Expected [1, 2], got {order}"


# ── Test 4: No-tool (reasoning) task → succeeds ───────────────────────────────

def test_no_tool_task_succeeds() -> None:
    plan = _make_plan(_task(1, tool=None))
    _executor().execute_plan(plan)

    assert plan.tasks[0].status == TaskStatus.COMPLETED
    assert plan.tasks[0].task_result.success is True
    assert plan.tasks[0].task_result.metadata.get("type") == "reasoning"


# ── Test 5: LLM tool → succeeds as pass-through ───────────────────────────────

def test_llm_tool_succeeds() -> None:
    plan = _make_plan(_task(1, tool="llm"))
    _executor().execute_plan(plan)

    assert plan.tasks[0].status == TaskStatus.COMPLETED


# ── Test 6: Failing tool → FAILED after max retries ──────────────────────────

def test_failing_tool_marks_failed() -> None:
    tm = MagicMock()
    tm.tools = {"bad_tool": _FailingTool()}
    executor = Executor(tool_manager=tm)
    plan     = _make_plan(_task(1, tool="bad_tool"))

    executor.execute_plan(plan)

    assert plan.tasks[0].status == TaskStatus.FAILED
    assert plan.tasks[0].task_result.success is False


# ── Test 7: Failed dependency → downstream task SKIPPED ──────────────────────

def test_failed_dependency_skips_downstream() -> None:
    tm = MagicMock()
    tm.tools = {"bad_tool": _FailingTool()}
    executor = Executor(tool_manager=tm)
    plan = _make_plan(
        _task(1, tool="bad_tool"),     # will fail
        _task(2, tool=None, deps=[1]), # should be skipped
    )
    executor.execute_plan(plan)

    assert plan.tasks[0].status == TaskStatus.FAILED
    assert plan.tasks[1].status == TaskStatus.SKIPPED


# ── Test 8: Empty plan → returned unchanged ───────────────────────────────────

def test_empty_plan_no_crash() -> None:
    plan = Plan(goal="nothing", tasks=[])
    result = _executor().execute_plan(plan)
    assert result is plan   # same object, no crash


# ── Test 9: Unknown tool → task FAILED ───────────────────────────────────────

def test_unknown_tool_fails() -> None:
    plan = _make_plan(_task(1, tool="nonexistent_tool"))
    _executor().execute_plan(plan)

    assert plan.tasks[0].status == TaskStatus.FAILED
    assert "Unknown tool" in plan.tasks[0].error


# ── Test 10: Retry count increments ──────────────────────────────────────────

def test_retry_count_increments() -> None:
    tm = MagicMock()
    tm.tools = {"bad_tool": _FailingTool()}
    executor = Executor(tool_manager=tm)
    plan     = _make_plan(_task(1, tool="bad_tool"))

    executor.execute_plan(plan)

    # retries should be > 0 because the task failed and was retried
    assert plan.tasks[0].retries > 0


# ── Test 11: Events published ─────────────────────────────────────────────────

def test_events_published() -> None:
    bus      = EventBus()
    received: list[str] = []

    for event in ("plan.started", "task.started", "task.completed", "plan.completed"):
        bus.subscribe(event, lambda data, e=event: received.append(e))

    executor = Executor(
        tool_manager = _make_tool_manager(),
        event_bus    = bus,
    )
    plan = _make_plan(_task(1, tool="calculator"))
    executor.execute_plan(plan)

    assert "plan.started"    in received
    assert "task.started"    in received
    assert "task.completed"  in received
    assert "plan.completed"  in received


# ── Test 12: Successful plan → status "completed" ────────────────────────────

def test_successful_plan_status() -> None:
    plan = _make_plan(_task(1, tool="calculator"), _task(2, tool=None, deps=[1]))
    _executor().execute_plan(plan)

    assert plan.status == "completed"


# ── Test 13: Failed plan → status "failed" ───────────────────────────────────

def test_failed_plan_status() -> None:
    tm = MagicMock()
    tm.tools = {"bad_tool": _FailingTool()}
    executor = Executor(tool_manager=tm)
    plan     = _make_plan(_task(1, tool="bad_tool"))

    executor.execute_plan(plan)

    assert plan.status == "failed"


# ── Test 14: execute_task returns TaskResult ─────────────────────────────────

def test_execute_task_returns_task_result() -> None:
    executor = _executor()
    plan     = _make_plan(_task(1, tool="calculator"))
    tracker  = ProgressTracker(plan)
    task     = plan.tasks[0]

    result = executor.execute_task(task, plan, tracker)

    from models.result import TaskResult
    assert isinstance(result, TaskResult)


# ── Test 15: Execution time is recorded ──────────────────────────────────────

def test_execution_time_recorded() -> None:
    plan = _make_plan(_task(1, tool="calculator"))
    _executor().execute_plan(plan)

    tr = plan.tasks[0].task_result
    assert tr is not None
    assert isinstance(tr.execution_time, float)
    assert tr.execution_time >= 0.0
