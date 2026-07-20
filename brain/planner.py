"""
brain/planner.py

The Planner — converts a user request into a structured, validated Plan.

Single responsibility:
    user input (str)  →  Plan  (validated, dependency-resolved, ready to execute)

The Planner does NOT execute anything.
It extracts a goal, asks the LLM to decompose it into Tasks, validates the
result, and returns a Plan. If the LLM produces a bad plan it retries up to
MAX_PLAN_RETRIES times before falling back to a minimal safe plan.

Pipeline:
    User input
        ↓
    _extract_goal()          — clean and normalise the goal string
        ↓
    _call_llm()              — ask the LLM to produce a JSON task list
        ↓
    _parse()                 — JSON → Plan object
        ↓
    PlanValidator.validate() — check IDs, descriptions, deps, tools, cycles
        ↓  (invalid → retry with errors fed back to LLM)
        ↓
    _log_execution_order()   — log the planned task sequence
        ↓
    Return Plan

Expected LLM JSON format:
    {
        "goal": "Analyse the repository",
        "tasks": [
            {
                "id": 1,
                "description": "Scan project files",
                "tool": "project_scanner",
                "priority": 2,
                "dependencies": []
            },
            {
                "id": 2,
                "description": "Generate README",
                "tool": "llm",
                "priority": 2,
                "dependencies": [1]
            }
        ]
    }
"""

from __future__ import annotations

import json
import re

import ollama

from brain.validator import PlanValidator, ValidationResult
from config.settings import DEFAULT_MODEL
from models.enums import TaskPriority, TaskStatus
from models.plan import Plan
from models.task import Task
from utils.logger import logger

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_PLAN_RETRIES:  int = 2    # Extra attempts after the first failure
MAX_GOAL_LENGTH:   int = 500  # Characters — trim very long inputs before sending


class Planner:
    """
    Generates a structured, validated Plan from a user goal.

    Dependencies injected at construction:
        known_tools: set of tool names from ToolManager — used by the validator
                     to reject plans that reference unknown tools.
    """

    def __init__(self, known_tools: set[str]) -> None:
        """
        Args:
            known_tools: Tool names registered in ToolManager
                         (e.g. {"calculator", "file_reader", "project_scanner"}).
        """
        self._known_tools = known_tools
        self._validator   = PlanValidator(known_tools)

    # ── Public API ────────────────────────────────────────────────────────────

    def create_plan(self, user_input: str) -> Plan:
        """
        Convert a user request into a validated, ready-to-execute Plan.

        Steps:
            1. Extract and normalise the goal.
            2. Ask the LLM for a JSON task list (retry on failure).
            3. Validate the plan.
            4. Log the execution order.
            5. Return the Plan.

        Falls back to a minimal two-task plan if all LLM attempts fail.

        Args:
            user_input: Raw natural-language request from the user.

        Returns:
            A valid Plan with populated tasks and dependencies.
        """
        # Step 1 — Extract goal
        goal = self._extract_goal(user_input)
        logger.info(f"Planner: goal = '{goal[:80]}'")

        last_errors: list[str] = []

        for attempt in range(1, MAX_PLAN_RETRIES + 2):   # initial + retries
            logger.debug(f"Planner: attempt {attempt}/{MAX_PLAN_RETRIES + 1}")

            # Step 2 — Call LLM
            raw = self._call_llm(goal, last_errors)
            plan = self._parse(goal, raw)

            if plan is None:
                last_errors = ["Could not parse LLM response as valid JSON."]
                logger.warning(f"Planner: attempt {attempt} — parse failed.")
                continue

            # Step 3 — Validate
            validation: ValidationResult = self._validator.validate(plan)

            if validation.valid:
                # Step 4 — Log execution order
                self._log_execution_order(plan)
                return plan

            last_errors = validation.errors
            logger.warning(
                f"Planner: attempt {attempt} invalid — "
                + "; ".join(last_errors)
            )

        # All attempts failed — use fallback
        logger.error("Planner: all attempts exhausted. Using fallback plan.")
        plan = self._fallback_plan(goal)
        self._log_execution_order(plan)
        return plan

    # ── Step 1 — Goal extraction ──────────────────────────────────────────────

    @staticmethod
    def _extract_goal(user_input: str) -> str:
        """
        Clean and normalise the user input into a concise goal string.

        - Strips leading/trailing whitespace
        - Collapses multiple spaces into one
        - Truncates to MAX_GOAL_LENGTH characters
        - Capitalises the first letter

        Examples:
            "  analyse my GitHub repo  "  →  "Analyse my GitHub repo"
            "read every PDF in documents and summarize them"  →  (unchanged)
        """
        if not user_input or not user_input.strip():
            return "Respond to the user"

        goal = " ".join(user_input.split())          # collapse whitespace
        goal = goal[:MAX_GOAL_LENGTH]                # truncate
        goal = goal[0].upper() + goal[1:]            # capitalise first letter
        return goal

    # ── Step 2 — LLM interaction ──────────────────────────────────────────────

    def _call_llm(self, goal: str, previous_errors: list[str]) -> str:
        """Send the planning prompt to the LLM and return the raw text response."""
        prompt = self._build_prompt(goal, previous_errors)
        try:
            response = ollama.chat(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return response["message"]["content"]
        except Exception as e:
            logger.exception(f"Planner: LLM call failed: {e}")
            return ""

    def _build_prompt(self, goal: str, previous_errors: list[str]) -> str:
        """
        Construct the planning prompt.
        Includes prior validation errors when retrying so the LLM can fix them.
        """
        tool_list = ", ".join(sorted(self._known_tools)) if self._known_tools else "none"

        priority_note = (
            "Priority values: 1=LOW, 2=NORMAL, 3=HIGH, 4=CRITICAL. "
            "Default to 2 unless the task is clearly time-sensitive."
        )

        error_section = ""
        if previous_errors:
            lines = "\n".join(f"  - {e}" for e in previous_errors)
            error_section = (
                f"\nYour previous plan was REJECTED. Fix these issues:\n"
                f"{lines}\n"
            )

        return f"""You are the planning engine for IRIS, an AI agent.

Decompose the following goal into 3–8 concrete, sequential tasks.
{error_section}
Goal: {goal}

Available tools: {tool_list}
{priority_note}

Rules:
- Return ONLY a raw JSON object. No markdown. No code fences. No explanation.
- Each task must have all five fields: id, description, tool, priority, dependencies.
- "tool": use a tool name from the list, "llm" for language generation, or null for reasoning steps.
- "dependencies": list of task IDs that must COMPLETE before this task starts. Use [] if none.
- Task IDs must be unique integers starting at 1.
- Do not create circular dependencies.

Required output format:
{{
  "goal": "{goal}",
  "tasks": [
    {{"id": 1, "description": "First step", "tool": null, "priority": 2, "dependencies": []}},
    {{"id": 2, "description": "Second step", "tool": "file_reader", "priority": 2, "dependencies": [1]}},
    {{"id": 3, "description": "Final step", "tool": "llm", "priority": 2, "dependencies": [2]}}
  ]
}}"""

    # ── Step 3 — Parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _parse(goal: str, raw: str) -> Plan | None:
        """
        Extract the JSON object from the LLM response and build a Plan.

        Handles:
        - Responses wrapped in ```json ... ``` fences
        - Extra text before/after the JSON block
        - Missing priority field (defaults to NORMAL)

        Returns None if no valid JSON can be extracted.
        """
        if not raw or not raw.strip():
            return None

        # Remove markdown fences
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # Extract the first complete {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.warning("Planner._parse: no JSON object found in LLM response.")
            return None

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.warning(f"Planner._parse: JSON decode error: {e}")
            return None

        raw_tasks = data.get("tasks", [])
        if not isinstance(raw_tasks, list):
            logger.warning("Planner._parse: 'tasks' field is not a list.")
            return None

        tasks: list[Task] = []
        for raw_task in raw_tasks:
            try:
                task = Task(
                    id           = int(raw_task["id"]),
                    description  = str(raw_task["description"]).strip(),
                    tool         = raw_task.get("tool") or None,
                    priority     = TaskPriority(
                                       int(raw_task.get("priority", TaskPriority.NORMAL.value))
                                   ),
                    dependencies = [int(d) for d in raw_task.get("dependencies", [])],
                    status       = TaskStatus.PENDING,
                )
                tasks.append(task)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Planner._parse: skipping malformed task {raw_task}: {e}")

        if not tasks:
            logger.warning("Planner._parse: no valid tasks parsed.")
            return None

        return Plan(
            goal     = goal,
            tasks    = tasks,
            metadata = {"model": DEFAULT_MODEL, "source": "llm"},
        )

    # ── Step 4 — Execution order logging ─────────────────────────────────────

    @staticmethod
    def _log_execution_order(plan: Plan) -> None:
        """
        Log the planned execution sequence after a valid plan is built.

        Uses topological sort to derive a safe execution order respecting
        dependencies, then logs each step.
        """
        logger.info(
            f"Plan created: {len(plan.tasks)} task(s) for '{plan.goal[:60]}'"
        )

        # Topological sort (Kahn's algorithm) to get execution order
        in_deg: dict[int, int]    = {t.id: len(t.dependencies) for t in plan.tasks}
        adj:    dict[int, list[int]] = {t.id: [] for t in plan.tasks}
        for task in plan.tasks:
            for dep in task.dependencies:
                if dep in adj:
                    adj[dep].append(task.id)

        queue  = [tid for tid, deg in in_deg.items() if deg == 0]
        order: list[int] = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbour in adj.get(node, []):
                in_deg[neighbour] -= 1
                if in_deg[neighbour] == 0:
                    queue.append(neighbour)

        # Log each step with tool annotation
        id_to_task = {t.id: t for t in plan.tasks}
        logger.info("Execution order:")
        for step, task_id in enumerate(order, 1):
            task = id_to_task.get(task_id)
            if task:
                tool_label = f" [{task.tool}]" if task.tool else ""
                logger.info(f"  Step {step}: [{task.id}] {task.description}{tool_label}")

    # ── Fallback plan ─────────────────────────────────────────────────────────

    @staticmethod
    def _fallback_plan(goal: str) -> Plan:
        """
        Minimal two-task plan returned when all LLM attempts fail.
        Guarantees the Workflow always has something to execute.
        """
        return Plan(
            goal     = goal,
            tasks    = [
                Task(
                    id          = 1,
                    description = "Understand the user's request",
                    tool        = None,
                    priority    = TaskPriority.NORMAL,
                    status      = TaskStatus.PENDING,
                ),
                Task(
                    id           = 2,
                    description  = "Generate a response using the LLM",
                    tool         = "llm",
                    priority     = TaskPriority.NORMAL,
                    status       = TaskStatus.PENDING,
                    dependencies = [1],
                ),
            ],
            metadata = {"source": "fallback"},
        )
