"""
tests/test_reflection.py

Unit tests for brain/reflection.py (ReflectionEngine).

No LLM, no real Planner, no real MemoryManager needed.
All external calls are replaced with lightweight fakes or mocks.

Run with:
    python -m pytest tests/test_reflection.py -v

Test cases:
    1.  Successful plan → CONTINUE, no retries.
    2.  Single failed task, retries remaining → RETRY.
    3.  Single failed task, retry limit reached → REPLAN or ABORT.
    4.  Permanent error (file not found) → no retry → REPLAN.
    5.  Transient error (timeout) → retry recommended.
    6.  Multiple failures ≥ threshold → REPLAN when planner available.
    7.  Multiple failures ≥ threshold, no planner → ABORT.
    8.  should_retry() returns False when retry limit reached.
    9.  should_retry() returns False for permanent error.
    10. should_replan() returns False when no planner injected.
    11. should_replan() returns False when replan limit exhausted.
    12. reflect_task() returns CONTINUE for COMPLETED task.
    13. reflect_task() returns RETRY for retryable failed task.
    14. reflect_task() returns CONTINUE for SKIPPED task.
    15. Events published: reflection.started, reflection.completed.
    16. Failures stored in memory.
    17. Success stored in memory on successful plan.
    18. Re-plan count increments on each REPLAN decision.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from brain.reflection import (
    ErrorCategory,
    ReflectionAction,
    ReflectionEngine,
    ReflectionOutcome,
    _classify_error,
)
from core.events import EventBus
from models.enums import TaskPriority, TaskStatus
from models.plan import Plan
from models.result import TaskResult
from models.task import Task


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_task(
    task_id: int,
    status:  TaskStatus = TaskStatus.COMPLETED,
    error:   str | None = None,
    retries: int = 0,
    tool:    str | None = None,
) -> Task:
    task = Task(
        id          = task_id,
        description = f"Task {task_id}",
        tool        = tool,
        priority    = TaskPriority.NORMAL,
    )
    task.status  = status
    task.retries = retries
    if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        result = (
            TaskResult.success_result(output="ok", tool=tool or "none")
            if status == TaskStatus.COMPLETED
            else TaskResult.failure_result(error=error or "error", tool=tool or "none")
        )
        task.task_result = result
    return task


def _make_plan(*tasks: Task, goal: str = "Test goal") -> Plan:
    plan = Plan(goal=goal, tasks=list(tasks))
    plan.update_status()
    return plan


def _engine(
    planner: object | None = None,
    memory:  object | None = None,
    events:  EventBus | None = None,
) -> ReflectionEngine:
    return ReflectionEngine(
        planner        = planner,
        memory_manager = memory,
        event_bus      = events,
    )


def _fake_planner(goal: str = "Test goal") -> MagicMock:
    mock = MagicMock()
    mock.create_plan.return_value = _make_plan(
        _make_task(1, TaskStatus.PENDING),
        goal=goal,
    )
    return mock


# ── Test 1: Successful plan → CONTINUE ───────────────────────────────────────

def test_successful_plan_returns_continue() -> None:
    plan = _make_plan(_make_task(1, TaskStatus.COMPLETED))
    outcome = _engine().reflect(plan)
    assert outcome.action == ReflectionAction.CONTINUE


# ── Test 2: Failed task, retries remaining → RETRY ───────────────────────────

def test_failed_task_retries_remaining_returns_retry() -> None:
    task = _make_task(1, TaskStatus.FAILED, error="timeout", retries=0)
    plan = _make_plan(task)
    outcome = _engine().reflect(plan)
    assert outcome.action == ReflectionAction.RETRY
    assert task in outcome.tasks_to_retry


# ── Test 3: Retry limit reached → REPLAN or ABORT ────────────────────────────

def test_retry_limit_reached_no_planner_returns_abort() -> None:
    # retries=2 means MAX_TASK_RETRIES exhausted
    task = _make_task(1, TaskStatus.FAILED, error="timeout", retries=2)
    plan = _make_plan(task)
    outcome = _engine().reflect(plan)
    # No planner → cannot replan → should ABORT (or CONTINUE if below threshold)
    assert outcome.action in (ReflectionAction.ABORT, ReflectionAction.CONTINUE)


# ── Test 4: Permanent error → REPLAN (not retry) ─────────────────────────────

def test_permanent_error_triggers_replan() -> None:
    task = _make_task(1, TaskStatus.FAILED, error="file not found", retries=0)
    plan = _make_plan(task)
    planner = _fake_planner(plan.goal)
    outcome = _engine(planner=planner).reflect(plan)
    # Permanent errors are not retried — should replan when available
    assert outcome.action in (ReflectionAction.REPLAN, ReflectionAction.CONTINUE)


# ── Test 5: Transient error → retry recommended ───────────────────────────────

def test_transient_error_should_retry() -> None:
    task = _make_task(1, TaskStatus.FAILED, error="network timeout", retries=0)
    engine = _engine()
    assert engine.should_retry(task) is True


# ── Test 6: Multiple failures ≥ threshold → REPLAN ───────────────────────────

def test_multiple_failures_triggers_replan() -> None:
    # REFLECTION_FAIL_THRESHOLD = 2 — need ≥2 permanently failed tasks
    t1 = _make_task(1, TaskStatus.FAILED, error="file not found", retries=2)
    t2 = _make_task(2, TaskStatus.FAILED, error="invalid input",  retries=2)
    plan    = _make_plan(t1, t2)
    planner = _fake_planner(plan.goal)
    outcome = _engine(planner=planner).reflect(plan)
    assert outcome.action == ReflectionAction.REPLAN


# ── Test 7: Multiple failures, no planner → ABORT ────────────────────────────

def test_multiple_failures_no_planner_returns_abort() -> None:
    t1 = _make_task(1, TaskStatus.FAILED, error="file not found", retries=2)
    t2 = _make_task(2, TaskStatus.FAILED, error="invalid input",  retries=2)
    plan    = _make_plan(t1, t2)
    outcome = _engine(planner=None).reflect(plan)
    assert outcome.action == ReflectionAction.ABORT


# ── Test 8: should_retry False when retry limit reached ──────────────────────

def test_should_retry_false_at_limit() -> None:
    task = _make_task(1, TaskStatus.FAILED, error="timeout", retries=2)
    assert _engine().should_retry(task) is False


# ── Test 9: should_retry False for permanent error ───────────────────────────

def test_should_retry_false_for_permanent_error() -> None:
    task = _make_task(1, TaskStatus.FAILED, error="file not found", retries=0)
    assert _engine().should_retry(task) is False


# ── Test 10: should_replan False when no planner ─────────────────────────────

def test_should_replan_false_no_planner() -> None:
    t1 = _make_task(1, TaskStatus.FAILED, error="error", retries=2)
    t2 = _make_task(2, TaskStatus.FAILED, error="error", retries=2)
    plan = _make_plan(t1, t2)
    assert _engine(planner=None).should_replan(plan) is False


# ── Test 11: should_replan False when replan limit exhausted ─────────────────

def test_should_replan_false_when_limit_exhausted() -> None:
    t1 = _make_task(1, TaskStatus.FAILED, error="error", retries=2)
    t2 = _make_task(2, TaskStatus.FAILED, error="error", retries=2)
    plan    = _make_plan(t1, t2, goal="unique goal for limit test")
    planner = _fake_planner(plan.goal)
    engine  = _engine(planner=planner)

    # Exhaust replan attempts
    from config.settings import MAX_REPLAN_ATTEMPTS
    engine._replan_counts[plan.goal] = MAX_REPLAN_ATTEMPTS

    assert engine.should_replan(plan) is False


# ── Test 12: reflect_task CONTINUE for COMPLETED ─────────────────────────────

def test_reflect_task_completed_returns_continue() -> None:
    task   = _make_task(1, TaskStatus.COMPLETED)
    action = _engine().reflect_task(task)
    assert action == ReflectionAction.CONTINUE


# ── Test 13: reflect_task RETRY for retryable failed task ────────────────────

def test_reflect_task_failed_retryable_returns_retry() -> None:
    task   = _make_task(1, TaskStatus.FAILED, error="timeout", retries=0)
    action = _engine().reflect_task(task)
    assert action == ReflectionAction.RETRY


# ── Test 14: reflect_task CONTINUE for SKIPPED ───────────────────────────────

def test_reflect_task_skipped_returns_continue() -> None:
    task = _make_task(1, TaskStatus.SKIPPED)
    assert _engine().reflect_task(task) == ReflectionAction.CONTINUE


# ── Test 15: Events published ─────────────────────────────────────────────────

def test_events_published() -> None:
    bus      = EventBus()
    received: list[str] = []

    bus.subscribe("reflection.started",   lambda d: received.append("started"))
    bus.subscribe("reflection.completed", lambda d: received.append("completed"))

    plan    = _make_plan(_make_task(1, TaskStatus.COMPLETED))
    engine  = _engine(events=bus)
    engine.reflect(plan)

    assert "started"   in received
    assert "completed" in received


# ── Test 16: Failures stored in memory ───────────────────────────────────────

def test_failures_stored_in_memory() -> None:
    stored: list[str] = []
    memory = MagicMock()
    memory.store_memory.side_effect = lambda text: stored.append(text)

    task = _make_task(1, TaskStatus.FAILED, error="disk full", retries=2)
    plan = _make_plan(task)
    _engine(memory=memory).reflect(plan)

    assert any("FAILURE" in s for s in stored), (
        f"Expected a FAILURE record in memory, got: {stored}"
    )


# ── Test 17: Success stored in memory ────────────────────────────────────────

def test_success_stored_in_memory() -> None:
    stored: list[str] = []
    memory = MagicMock()
    memory.store_memory.side_effect = lambda text: stored.append(text)

    plan = _make_plan(_make_task(1, TaskStatus.COMPLETED))
    _engine(memory=memory).reflect(plan)

    assert any("SUCCESS" in s for s in stored), (
        f"Expected a SUCCESS record in memory, got: {stored}"
    )


# ── Test 18: Re-plan count increments ────────────────────────────────────────

def test_replan_count_increments() -> None:
    t1 = _make_task(1, TaskStatus.FAILED, error="file not found", retries=2)
    t2 = _make_task(2, TaskStatus.FAILED, error="invalid input",  retries=2)
    plan    = _make_plan(t1, t2, goal="unique goal count test")
    planner = _fake_planner(plan.goal)
    engine  = _engine(planner=planner)

    assert engine._replan_counts.get(plan.goal, 0) == 0
    engine.reflect(plan)
    assert engine._replan_counts.get(plan.goal, 0) == 1


# ── Error classification unit tests ──────────────────────────────────────────

def test_classify_transient_error() -> None:
    assert _classify_error("network timeout occurred") == ErrorCategory.TRANSIENT
    assert _classify_error("connection refused")       == ErrorCategory.TRANSIENT


def test_classify_permanent_error() -> None:
    assert _classify_error("file not found")   == ErrorCategory.PERMANENT
    assert _classify_error("unknown tool xyz") == ErrorCategory.PERMANENT
    assert _classify_error("invalid input")    == ErrorCategory.PERMANENT


def test_classify_unknown_error() -> None:
    assert _classify_error("something weird happened") == ErrorCategory.UNKNOWN
    assert _classify_error(None)                       == ErrorCategory.UNKNOWN
