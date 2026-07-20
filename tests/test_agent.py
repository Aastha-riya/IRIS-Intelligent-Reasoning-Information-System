"""
tests/test_agent.py

Unit tests for core/agent.py (AutonomousAgent).

No LLM, no real tools, no real WorkflowEngine needed.
All external calls are replaced with lightweight fakes.

Run with:
    python -m pytest tests/test_agent.py -v

Test cases:
    1.  Simple direct-answer goal → COMPLETED via LLM.
    2.  Tool goal (calculate) → COMPLETED via tool.
    3.  Plan goal (analyse) → COMPLETED via workflow.
    4.  Destructive goal → FAILED with safety message.
    5.  run() always returns AgentResult.
    6.  AgentResult.succeeded() True on COMPLETED.
    7.  No LLM, no tools, no workflow → FAILED after iterations.
    8.  Stopped agent rejects new goals.
    9.  pause() sets status to PAUSED.
    10. resume() sets status back to RUNNING after pause.
    11. stop() sets status to STOPPED permanently.
    12. step() returns meaningful string.
    13. Events published: agent.started, agent.goal_completed.
    14. Learning stored in memory on success.
    15. active_goal_count decrements after completion.
    16. Multi-step goal via workflow with successful plan.
    17. _reason() returns TOOL for calculator input.
    18. _reason() returns PLAN for 'analyse' input.
    19. _reason() returns CLARIFY for empty/vague input.
    20. _is_destructive() detects destructive keywords.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.agent import AgentStatus, AutonomousAgent, DecisionType, GoalStatus
from core.events import EventBus
from core.workflow import WorkflowResult, WorkflowStatus
from models.enums import TaskPriority, TaskStatus
from models.plan import Plan
from models.result import TaskResult
from models.task import Task


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_llm(response: str = "LLM answer") -> MagicMock:
    mock = MagicMock()
    mock.chat.return_value = response
    return mock


def _fake_tools(result: str | None = "tool result") -> MagicMock:
    mock = MagicMock()
    mock.execute.return_value = result
    return mock


def _fake_workflow(success: bool = True, output: str = "workflow done") -> MagicMock:
    task = Task(id=1, description="Done", priority=TaskPriority.NORMAL)
    task.status      = TaskStatus.COMPLETED
    task.task_result = TaskResult.success_result(output=output)
    plan = Plan(goal="test", tasks=[task])
    plan.update_status()

    wf_result = WorkflowResult(
        workflow_id = "test-wf",
        goal        = "test",
        status      = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED,
        plan        = plan if success else None,
        cycles      = 1,
    )
    mock = MagicMock()
    mock.run.return_value = wf_result
    return mock


def _agent(
    llm:      object | None = None,
    tools:    object | None = None,
    workflow: object | None = None,
    memory:   object | None = None,
    events:   EventBus | None = None,
) -> AutonomousAgent:
    return AutonomousAgent(
        llm            = llm,
        tool_manager   = tools,
        workflow       = workflow,
        memory_manager = memory,
        event_bus      = events,
    )


# ── Test 1: Direct LLM goal → COMPLETED ──────────────────────────────────────

def test_direct_goal_completes() -> None:
    agent  = _agent(llm=_fake_llm("Hello!"))
    result = agent.run("What is AI?")
    assert result.status == GoalStatus.COMPLETED
    assert result.output == "Hello!"
    assert result.decision == DecisionType.DIRECT


# ── Test 2: Tool goal → COMPLETED via tool ───────────────────────────────────

def test_tool_goal_uses_tool() -> None:
    agent  = _agent(tools=_fake_tools("42"))
    result = agent.run("calculate 6 * 7")
    assert result.status == GoalStatus.COMPLETED
    assert result.decision == DecisionType.TOOL
    assert "42" in result.output


# ── Test 3: Plan goal → COMPLETED via workflow ───────────────────────────────

def test_plan_goal_uses_workflow() -> None:
    agent  = _agent(workflow=_fake_workflow(True, "Analysis done"))
    result = agent.run("analyse the repository")
    assert result.status == GoalStatus.COMPLETED
    assert result.decision == DecisionType.PLAN


# ── Test 4: Destructive goal → FAILED with safety error ──────────────────────

def test_destructive_goal_blocked() -> None:
    agent  = _agent(llm=_fake_llm())
    result = agent.run("delete all files in the project")
    assert result.status == GoalStatus.FAILED
    assert "destructive" in result.error.lower()


# ── Test 5: run() always returns AgentResult ─────────────────────────────────

def test_run_always_returns_agent_result() -> None:
    from core.agent import AgentResult
    result = _agent().run("something")
    assert isinstance(result, AgentResult)


# ── Test 6: succeeded() True on COMPLETED ────────────────────────────────────

def test_succeeded_true_on_completed() -> None:
    agent  = _agent(llm=_fake_llm("answer"))
    result = agent.run("simple question")
    assert result.succeeded() is True


# ── Test 7: No handlers → FAILED after iterations ────────────────────────────

def test_no_handlers_returns_failed() -> None:
    # No LLM, no tools, no workflow
    agent  = _agent()
    result = agent.run("do something complex")
    assert result.status == GoalStatus.FAILED


# ── Test 8: Stopped agent rejects goals ──────────────────────────────────────

def test_stopped_agent_rejects_goals() -> None:
    agent = _agent(llm=_fake_llm())
    agent.stop()
    result = agent.run("anything")
    assert result.status == GoalStatus.FAILED
    assert "stopped" in result.error.lower()


# ── Test 9: pause() sets PAUSED ──────────────────────────────────────────────

def test_pause_sets_paused() -> None:
    agent = _agent()
    agent._status = AgentStatus.RUNNING
    agent.pause()
    assert agent.status == AgentStatus.PAUSED


# ── Test 10: resume() clears PAUSED ──────────────────────────────────────────

def test_resume_clears_paused() -> None:
    agent = _agent()
    agent._status = AgentStatus.PAUSED
    agent.resume()
    assert agent.status == AgentStatus.RUNNING


# ── Test 11: stop() is permanent ─────────────────────────────────────────────

def test_stop_is_permanent() -> None:
    agent = _agent()
    agent.stop()
    assert agent.status == AgentStatus.STOPPED
    agent.resume()   # should have no effect
    assert agent.status == AgentStatus.STOPPED


# ── Test 12: step() returns string ───────────────────────────────────────────

def test_step_returns_string() -> None:
    agent = _agent()
    result = agent.step()
    assert isinstance(result, str)
    assert len(result) > 0


# ── Test 13: Events published ─────────────────────────────────────────────────

def test_events_published() -> None:
    bus      = EventBus()
    received: list[str] = []
    bus.subscribe("agent.started",        lambda d: received.append("started"))
    bus.subscribe("agent.goal_completed", lambda d: received.append("completed"))

    agent  = _agent(llm=_fake_llm("hi"), events=bus)
    agent.run("say hello")

    assert "started"   in received
    assert "completed" in received


# ── Test 14: Learning stored in memory on success ─────────────────────────────

def test_learning_stored_on_success() -> None:
    stored: list[str] = []
    memory = MagicMock()
    memory.retrieve_memory.return_value = []
    memory.store_memory.side_effect = lambda t: stored.append(t)

    agent = _agent(llm=_fake_llm("learned answer"), memory=memory)
    agent.run("teach me something")

    assert any("AGENT SUCCESS" in s for s in stored)


# ── Test 15: active_goal_count decrements after completion ───────────────────

def test_active_goal_count_decrements() -> None:
    agent  = _agent(llm=_fake_llm("done"))
    assert agent.active_goal_count == 0
    agent.run("any goal")
    assert agent.active_goal_count == 0   # cleared after completion


# ── Test 16: Multi-step workflow with successful plan ─────────────────────────

def test_multi_step_workflow_succeeds() -> None:
    wf = _fake_workflow(success=True, output="step output")
    agent  = _agent(workflow=wf)
    result = agent.run("generate a full report")
    assert result.status == GoalStatus.COMPLETED
    assert result.decision == DecisionType.PLAN


# ── Test 17: _reason TOOL for calculator ─────────────────────────────────────

def test_reason_tool_for_calculator() -> None:
    agent  = _agent()
    assert agent._reason("calculate 10 + 5") == DecisionType.TOOL
    assert agent._reason("read file.txt")    == DecisionType.TOOL


# ── Test 18: _reason PLAN for analyse ────────────────────────────────────────

def test_reason_plan_for_analyse() -> None:
    agent = _agent()
    assert agent._reason("analyse this codebase") == DecisionType.PLAN
    assert agent._reason("create a README file")  == DecisionType.PLAN


# ── Test 19: _reason CLARIFY for vague input ─────────────────────────────────

def test_reason_clarify_for_vague() -> None:
    agent = _agent()
    assert agent._reason("?")    == DecisionType.CLARIFY
    assert agent._reason("help") == DecisionType.CLARIFY
    assert agent._reason("hi")   == DecisionType.CLARIFY


# ── Test 20: _is_destructive detects keywords ────────────────────────────────

def test_is_destructive_detects_keywords() -> None:
    agent = _agent()
    assert agent._is_destructive("delete all files") is True
    assert agent._is_destructive("remove the folder") is True
    assert agent._is_destructive("what is Python?") is False
    assert agent._is_destructive("read file.txt") is False
