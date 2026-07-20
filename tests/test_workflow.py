"""
tests/test_workflow.py

Unit tests for core/workflow.py (WorkflowEngine).

No LLM, no real tools needed — all external calls use lightweight fakes.

Run with:
    python -m pytest tests/test_workflow.py -v

Test cases:
    1.  Simple goal with successful plan → WorkflowStatus.COMPLETED.
    2.  run() always returns a WorkflowResult.
    3.  WorkflowResult.succeeded() True on completion.
    4.  No Planner, no existing plan → WorkflowStatus.FAILED.
    5.  Reflection ABORT → WorkflowStatus.FAILED.
    6.  Reflection RETRY resets failed tasks and re-runs.
    7.  Reflection REPLAN with new plan → second execution.
    8.  resume() continues a paused plan.
    9.  pause() sets state to PAUSED.
    10. cancel() sets state to CANCELLED.
    11. total_time is recorded and > 0.
    12. Workflow history stored in memory on completion.
    13. Events published: workflow.started, workflow.completed.
    14. MAX_WORKFLOW_CYCLES prevents infinite loops.
    15. WorkflowResult.cycles reflects actual cycle count.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from brain.reflection import ReflectionAction, ReflectionOutcome
from core.events import EventBus
from core.workflow import WorkflowEngine, WorkflowStatus
from models.enums import TaskPriority, TaskStatus
from models.plan import Plan
from models.result import TaskResult
from models.task import Task


# ── Helpers ───────────────────────────────────────────────────────────────────

def _task(tid: int, status: TaskStatus = TaskStatus.PENDING, tool: str | None = None) -> Task:
    t = Task(id=tid, description=f"Task {tid}", tool=tool, priority=TaskPriority.NORMAL)
    t.status = status
    if status == TaskStatus.COMPLETED:
        t.task_result = TaskResult.success_result(output="ok", tool=tool or "none")
    elif status == TaskStatus.FAILED:
        t.task_result = TaskResult.failure_result(error="error", tool=tool or "none")
    return t


def _successful_plan(goal: str = "Test goal") -> Plan:
    t = _task(1, TaskStatus.COMPLETED)
    p = Plan(goal=goal, tasks=[t])
    p.update_status()
    return p


def _failed_plan(goal: str = "Test goal") -> Plan:
    t = _task(1, TaskStatus.FAILED)
    p = Plan(goal=goal, tasks=[t])
    p.update_status()
    return p


def _fake_planner(plan: Plan) -> MagicMock:
    mock = MagicMock()
    mock.create_plan.return_value = plan
    return mock


def _fake_executor(plan: Plan) -> MagicMock:
    """Executor that always returns the given plan unchanged."""
    mock = MagicMock()
    mock.execute_plan.return_value = plan
    return mock


def _fake_reflection(action: ReflectionAction, new_plan: Plan | None = None) -> MagicMock:
    outcome = ReflectionOutcome(
        action   = action,
        new_plan = new_plan,
        reason   = f"test: {action.value}",
        summary  = f"test summary: {action.value}",
    )
    mock = MagicMock()
    mock.reflect.return_value = outcome
    return mock


def _engine(
    planner:    object | None = None,
    executor:   object | None = None,
    reflection: object | None = None,
    memory:     object | None = None,
    events:     EventBus | None = None,
) -> WorkflowEngine:
    return WorkflowEngine(
        planner        = planner,
        executor       = executor,
        reflection     = reflection,
        memory_manager = memory,
        event_bus      = events,
    )


# ── Test 1: Successful plan → COMPLETED ──────────────────────────────────────

def test_successful_plan_completes() -> None:
    plan = _successful_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
    )
    result = engine.run("test goal")
    assert result.status == WorkflowStatus.COMPLETED


# ── Test 2: run() always returns WorkflowResult ───────────────────────────────

def test_run_always_returns_result() -> None:
    from core.workflow import WorkflowResult
    engine = _engine()
    result = engine.run("anything")
    assert isinstance(result, WorkflowResult)


# ── Test 3: succeeded() True on COMPLETED ────────────────────────────────────

def test_succeeded_true_on_completed() -> None:
    plan = _successful_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
    )
    result = engine.run("goal")
    assert result.succeeded() is True


# ── Test 4: No planner, no plan → FAILED ─────────────────────────────────────

def test_no_planner_returns_failed() -> None:
    result = _engine().run("goal")
    assert result.status == WorkflowStatus.FAILED


# ── Test 5: Reflection ABORT → FAILED ────────────────────────────────────────

def test_abort_reflection_returns_failed() -> None:
    plan = _failed_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.ABORT),
    )
    result = engine.run("goal")
    assert result.status == WorkflowStatus.FAILED


# ── Test 6: Reflection RETRY resets tasks and re-runs ────────────────────────

def test_retry_resets_failed_tasks() -> None:
    """
    Cycle 1: plan fails → RETRY.
    Cycle 2: plan succeeds → COMPLETED.
    """
    failed = _failed_plan("retry goal")
    success = _successful_plan("retry goal")

    call_count = {"n": 0}

    def execute_side_effect(plan):
        call_count["n"] += 1
        return success if call_count["n"] >= 2 else failed

    mock_exec = MagicMock()
    mock_exec.execute_plan.side_effect = execute_side_effect

    retry_task = _task(1, TaskStatus.FAILED)
    retry_outcome  = ReflectionOutcome(
        action=ReflectionAction.RETRY,
        tasks_to_retry=[retry_task],
        reason="retry test",
    )
    continue_outcome = ReflectionOutcome(action=ReflectionAction.CONTINUE, reason="done")

    reflect_call = {"n": 0}
    def reflect_side(plan):
        reflect_call["n"] += 1
        return retry_outcome if reflect_call["n"] == 1 else continue_outcome

    mock_reflect = MagicMock()
    mock_reflect.reflect.side_effect = reflect_side

    engine = _engine(
        planner    = _fake_planner(success),
        executor   = mock_exec,
        reflection = mock_reflect,
    )
    result = engine.run("retry goal")
    assert result.status == WorkflowStatus.COMPLETED
    assert result.cycles >= 2


# ── Test 7: Reflection REPLAN switches to new plan ───────────────────────────

def test_replan_uses_new_plan() -> None:
    failed_plan  = _failed_plan("replan goal")
    success_plan = _successful_plan("replan goal")

    call_count = {"n": 0}
    def execute_side(plan):
        call_count["n"] += 1
        return success_plan if call_count["n"] >= 2 else failed_plan

    mock_exec = MagicMock()
    mock_exec.execute_plan.side_effect = execute_side

    replan_outcome  = ReflectionOutcome(
        action=ReflectionAction.REPLAN, new_plan=success_plan, reason="replan"
    )
    continue_outcome = ReflectionOutcome(action=ReflectionAction.CONTINUE, reason="done")

    reflect_call = {"n": 0}
    def reflect_side(plan):
        reflect_call["n"] += 1
        return replan_outcome if reflect_call["n"] == 1 else continue_outcome

    mock_reflect = MagicMock()
    mock_reflect.reflect.side_effect = reflect_side

    engine = _engine(
        planner    = _fake_planner(failed_plan),
        executor   = mock_exec,
        reflection = mock_reflect,
    )
    result = engine.run("replan goal")
    assert result.status == WorkflowStatus.COMPLETED


# ── Test 8: resume() continues a paused plan ─────────────────────────────────

def test_resume_continues_plan() -> None:
    plan = _successful_plan("resume goal")
    engine = _engine(
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
    )
    result = engine.resume(plan)
    assert result.status == WorkflowStatus.COMPLETED


# ── Test 9: pause() sets state to PAUSED ─────────────────────────────────────

def test_pause_sets_paused_state() -> None:
    plan   = _successful_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
    )
    # Create a state by registering one manually
    from core.workflow import WorkflowState, WorkflowStatus
    import uuid
    wid   = str(uuid.uuid4())
    state = WorkflowState(workflow_id=wid, goal="test", status=WorkflowStatus.RUNNING)
    engine._states[wid] = state

    result = engine.pause(wid)
    assert result is True
    assert state.status == WorkflowStatus.PAUSED


# ── Test 10: cancel() sets state to CANCELLED ────────────────────────────────

def test_cancel_sets_cancelled_state() -> None:
    from core.workflow import WorkflowState, WorkflowStatus
    import uuid
    engine = _engine()
    wid    = str(uuid.uuid4())
    state  = WorkflowState(workflow_id=wid, goal="test", status=WorkflowStatus.RUNNING)
    engine._states[wid] = state

    result = engine.cancel(wid)
    assert result is True
    assert state.status == WorkflowStatus.CANCELLED


# ── Test 11: total_time is recorded ──────────────────────────────────────────

def test_total_time_recorded() -> None:
    plan = _successful_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
    )
    result = engine.run("goal")
    assert isinstance(result.total_time, float)
    assert result.total_time >= 0.0


# ── Test 12: History stored in memory ────────────────────────────────────────

def test_history_stored_in_memory() -> None:
    stored: list[str] = []
    memory = MagicMock()
    memory.store_memory.side_effect = lambda t: stored.append(t)

    plan = _successful_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
        memory     = memory,
    )
    engine.run("history test")
    assert any("WORKFLOW" in s for s in stored)


# ── Test 13: Events published ─────────────────────────────────────────────────

def test_events_published() -> None:
    bus      = EventBus()
    received: list[str] = []
    bus.subscribe("workflow.started",   lambda d: received.append("started"))
    bus.subscribe("workflow.completed", lambda d: received.append("completed"))

    plan = _successful_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
        events     = bus,
    )
    engine.run("event test")
    assert "started"   in received
    assert "completed" in received


# ── Test 14: MAX_WORKFLOW_CYCLES prevents infinite loops ──────────────────────

def test_max_cycles_prevents_infinite_loop() -> None:
    # Always return RETRY so the loop keeps going
    plan = _failed_plan("infinite loop test")
    retry_task = _task(1, TaskStatus.FAILED)

    mock_exec = MagicMock()
    mock_exec.execute_plan.return_value = plan

    mock_reflect = MagicMock()
    mock_reflect.reflect.return_value = ReflectionOutcome(
        action         = ReflectionAction.RETRY,
        tasks_to_retry = [retry_task],
        reason         = "always retry",
    )

    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = mock_exec,
        reflection = mock_reflect,
    )
    result = engine.run("infinite loop test")
    # Must terminate — either FAILED (cycle limit) or some terminal state
    assert result.status in (WorkflowStatus.FAILED, WorkflowStatus.COMPLETED)


# ── Test 15: cycles count is accurate ────────────────────────────────────────

def test_cycles_count_accurate() -> None:
    plan = _successful_plan()
    engine = _engine(
        planner    = _fake_planner(plan),
        executor   = _fake_executor(plan),
        reflection = _fake_reflection(ReflectionAction.CONTINUE),
    )
    result = engine.run("cycle count test")
    assert result.cycles == 1
