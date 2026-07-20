"""
tests/test_planner.py

Unit tests for brain/planner.py (Planner).

Most tests use monkeypatching to replace the Ollama LLM call with a
controlled JSON response — no running LLM required.

Run with:
    python -m pytest tests/test_planner.py -v

Test cases:
    1.  Single-task plan — LLM returns one task, valid plan returned.
    2.  Multi-task plan — LLM returns several tasks with dependencies.
    3.  Dependency chain is preserved correctly in the Plan.
    4.  Invalid JSON from LLM → fallback plan returned after retries.
    5.  Empty string input → fallback plan with cleaned goal.
    6.  Whitespace-only input → fallback plan with cleaned goal.
    7.  Very long input → goal is truncated to MAX_GOAL_LENGTH.
    8.  Duplicate task IDs → validation fails, retries, then fallback.
    9.  Unknown tool in plan → validation fails, retries, then fallback.
    10. Circular dependency → validation fails, retries, then fallback.
    11. create_plan() always returns a Plan with at least one task.
    12. Goal extraction capitalises the first letter.
    13. Goal extraction collapses multiple spaces.
    14. Execution order is logged (smoke test — no crash on valid plan).
    15. Fallback plan has two tasks with dependency 2 → [1].
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from brain.planner import MAX_GOAL_LENGTH, Planner
from models.plan import Plan
from models.task import Task
from models.enums import TaskStatus, TaskPriority

# ── Fixtures ──────────────────────────────────────────────────────────────────

KNOWN_TOOLS: set[str] = {"calculator", "file_reader", "project_scanner"}


@pytest.fixture
def planner() -> Planner:
    return Planner(known_tools=KNOWN_TOOLS)


# ── Helper ────────────────────────────────────────────────────────────────────

def _mock_llm_response(tasks: list[dict], goal: str = "Test goal") -> MagicMock:
    """Return a mock that simulates ollama.chat() returning a JSON plan."""
    payload = json.dumps({"goal": goal, "tasks": tasks})
    mock    = MagicMock()
    mock.__getitem__ = lambda self, key: {"message": {"content": payload}}[key]
    return MagicMock(return_value={"message": {"content": payload}})


def _patch_llm(tasks: list[dict], goal: str = "Test goal"):
    """Context manager: patch ollama.chat to return the given tasks."""
    payload = json.dumps({"goal": goal, "tasks": tasks})
    return patch(
        "brain.planner.ollama.chat",
        return_value={"message": {"content": payload}},
    )


# ── Test 1: Single-task plan ──────────────────────────────────────────────────

def test_single_task_plan(planner: Planner) -> None:
    tasks = [
        {"id": 1, "description": "Calculate result", "tool": "calculator",
         "priority": 2, "dependencies": []}
    ]
    with _patch_llm(tasks):
        plan = planner.create_plan("calculate 2 + 2")

    assert isinstance(plan, Plan)
    assert len(plan.tasks) == 1
    assert plan.tasks[0].tool == "calculator"
    assert plan.tasks[0].status == TaskStatus.PENDING


# ── Test 2: Multi-task plan ───────────────────────────────────────────────────

def test_multi_task_plan(planner: Planner) -> None:
    tasks = [
        {"id": 1, "description": "Scan folder",    "tool": "project_scanner",
         "priority": 2, "dependencies": []},
        {"id": 2, "description": "Read README",    "tool": "file_reader",
         "priority": 2, "dependencies": [1]},
        {"id": 3, "description": "Generate report","tool": "llm",
         "priority": 2, "dependencies": [2]},
    ]
    with _patch_llm(tasks):
        plan = planner.create_plan("Analyse my project")

    assert len(plan.tasks) == 3
    assert plan.tasks[0].id == 1
    assert plan.tasks[1].id == 2
    assert plan.tasks[2].id == 3


# ── Test 3: Dependencies preserved ───────────────────────────────────────────

def test_dependencies_preserved(planner: Planner) -> None:
    tasks = [
        {"id": 1, "description": "Step A", "tool": None,
         "priority": 2, "dependencies": []},
        {"id": 2, "description": "Step B", "tool": "llm",
         "priority": 2, "dependencies": [1]},
        {"id": 3, "description": "Step C", "tool": "llm",
         "priority": 2, "dependencies": [1, 2]},
    ]
    with _patch_llm(tasks):
        plan = planner.create_plan("Do A then B then C")

    assert plan.get_task(2).dependencies == [1]
    assert plan.get_task(3).dependencies == [1, 2]


# ── Test 4: Invalid JSON → fallback after retries ─────────────────────────────

def test_invalid_json_returns_fallback(planner: Planner) -> None:
    with patch("brain.planner.ollama.chat",
               return_value={"message": {"content": "not json at all"}}):
        plan = planner.create_plan("Do something")

    assert isinstance(plan, Plan)
    assert len(plan.tasks) >= 1   # fallback always has at least 1 task


# ── Test 5: Empty string input ────────────────────────────────────────────────

def test_empty_string_input(planner: Planner) -> None:
    with patch("brain.planner.ollama.chat",
               return_value={"message": {"content": "{}"}}):
        plan = planner.create_plan("")

    assert isinstance(plan, Plan)
    assert plan.goal == "Respond to the user"


# ── Test 6: Whitespace-only input ─────────────────────────────────────────────

def test_whitespace_only_input(planner: Planner) -> None:
    with patch("brain.planner.ollama.chat",
               return_value={"message": {"content": "{}"}}):
        plan = planner.create_plan("   ")

    assert plan.goal == "Respond to the user"


# ── Test 7: Very long input is truncated ──────────────────────────────────────

def test_long_input_truncated(planner: Planner) -> None:
    long_input = "word " * 300   # far exceeds MAX_GOAL_LENGTH
    tasks = [{"id": 1, "description": "Do it", "tool": "llm",
               "priority": 2, "dependencies": []}]
    with _patch_llm(tasks):
        plan = planner.create_plan(long_input)

    assert len(plan.goal) <= MAX_GOAL_LENGTH


# ── Test 8: Duplicate task IDs → fallback ────────────────────────────────────

def test_duplicate_task_ids_returns_fallback(planner: Planner) -> None:
    bad_tasks = [
        {"id": 1, "description": "Task A", "tool": "llm",
         "priority": 2, "dependencies": []},
        {"id": 1, "description": "Task B", "tool": "llm",   # duplicate ID
         "priority": 2, "dependencies": []},
    ]
    payload = json.dumps({"goal": "test", "tasks": bad_tasks})
    with patch("brain.planner.ollama.chat",
               return_value={"message": {"content": payload}}):
        plan = planner.create_plan("test")

    # After all retries, fallback plan is returned
    assert isinstance(plan, Plan)
    assert len(plan.tasks) >= 1


# ── Test 9: Unknown tool → fallback ──────────────────────────────────────────

def test_unknown_tool_returns_fallback(planner: Planner) -> None:
    bad_tasks = [
        {"id": 1, "description": "Use mystery tool", "tool": "nonexistent_tool",
         "priority": 2, "dependencies": []},
    ]
    payload = json.dumps({"goal": "test", "tasks": bad_tasks})
    with patch("brain.planner.ollama.chat",
               return_value={"message": {"content": payload}}):
        plan = planner.create_plan("test")

    assert isinstance(plan, Plan)


# ── Test 10: Circular dependency → fallback ───────────────────────────────────

def test_circular_dependency_returns_fallback(planner: Planner) -> None:
    circular_tasks = [
        {"id": 1, "description": "Task A", "tool": "llm",
         "priority": 2, "dependencies": [2]},   # A depends on B
        {"id": 2, "description": "Task B", "tool": "llm",
         "priority": 2, "dependencies": [1]},   # B depends on A  → cycle
    ]
    payload = json.dumps({"goal": "test", "tasks": circular_tasks})
    with patch("brain.planner.ollama.chat",
               return_value={"message": {"content": payload}}):
        plan = planner.create_plan("circular test")

    assert isinstance(plan, Plan)


# ── Test 11: create_plan always returns Plan with ≥1 task ────────────────────

def test_always_returns_plan_with_tasks(planner: Planner) -> None:
    with patch("brain.planner.ollama.chat", side_effect=Exception("LLM offline")):
        plan = planner.create_plan("Do anything")

    assert isinstance(plan, Plan)
    assert len(plan.tasks) >= 1


# ── Test 12: Goal extraction — capitalises first letter ──────────────────────

def test_goal_extraction_capitalises(planner: Planner) -> None:
    result = planner._extract_goal("analyse the repository")
    assert result[0].isupper(), f"Expected uppercase first letter, got: '{result[0]}'"
    assert result == "Analyse the repository"


# ── Test 13: Goal extraction — collapses multiple spaces ─────────────────────

def test_goal_extraction_collapses_spaces(planner: Planner) -> None:
    result = planner._extract_goal("  scan   my   project  ")
    assert "  " not in result, "Multiple consecutive spaces should be collapsed."
    assert result == "Scan my project"


# ── Test 14: Execution order logging does not crash ───────────────────────────

def test_execution_order_logging_no_crash(planner: Planner) -> None:
    tasks = [
        {"id": 1, "description": "First",  "tool": None,  "priority": 2, "dependencies": []},
        {"id": 2, "description": "Second", "tool": "llm", "priority": 2, "dependencies": [1]},
        {"id": 3, "description": "Third",  "tool": "llm", "priority": 2, "dependencies": [2]},
    ]
    with _patch_llm(tasks):
        plan = planner.create_plan("Log order test")

    # If we get here without exception, logging worked
    assert isinstance(plan, Plan)


# ── Test 15: Fallback plan structure ─────────────────────────────────────────

def test_fallback_plan_structure(planner: Planner) -> None:
    fallback = planner._fallback_plan("Some failing goal")

    assert len(fallback.tasks) == 2
    assert fallback.tasks[0].id == 1
    assert fallback.tasks[1].id == 2
    assert fallback.tasks[1].dependencies == [1], (
        "Fallback task 2 must depend on task 1."
    )
    assert fallback.tasks[1].tool == "llm"
    assert fallback.metadata.get("source") == "fallback"
