"""
brain/planner.py

The brain of the IRIS agent — decomposes a user goal into an executable Plan.

Single responsibility:
    user goal (str)  →  Plan (validated, structured)

The Planner does NOT execute anything.
It asks the LLM to produce a JSON task list, validates it, and returns a Plan.

Pipeline:
    User goal
        ↓
    Build planning prompt
        ↓
    LLM → JSON response
        ↓
    Parse JSON → Plan
        ↓
    PlanValidator
        ↓  (if invalid → retry up to MAX_PLAN_RETRIES)
        ↓
    Return valid Plan

LLM output format expected:
    {
        "goal": "...",
        "tasks": [
            {
                "id": 1,
                "description": "...",
                "tool": "calculator" | "file_reader" | "llm" | null,
                "dependencies": []
            },
            ...
        ]
    }
"""

import json
import re

import ollama

from brain.validator import PlanValidator, ValidationResult
from config.settings import DEFAULT_MODEL
from models.plan import Plan
from models.task import Task
from utils.logger import logger

MAX_PLAN_RETRIES: int = 2   # How many times to ask the LLM to fix a bad plan


class Planner:
    """
    Generates a structured, validated Plan from a user goal.
    Requires the set of available tool names to validate generated plans.
    """

    def __init__(self, known_tools: set[str]) -> None:
        """
        Args:
            known_tools: Tool names from ToolManager
                         (e.g. {"calculator", "file_reader", "project_scanner"}).
        """
        self._validator  = PlanValidator(known_tools)
        self._known_tools = known_tools

    # ── Public API ────────────────────────────────────────────────────────────

    def create_plan(self, goal: str) -> Plan:
        """
        Generate and return a validated Plan for the given goal.

        Retries up to MAX_PLAN_RETRIES times if the LLM produces an invalid plan.
        Falls back to a minimal safe plan if all retries fail.

        Args:
            goal: The user's natural-language request.

        Returns:
            A valid Plan ready for the Workflow to execute.
        """
        logger.info(f"Planning for goal: '{goal[:80]}'")

        last_errors: list[str] = []

        for attempt in range(1, MAX_PLAN_RETRIES + 2):   # +2 → initial + retries
            logger.debug(f"Planner: attempt {attempt}")

            raw_json = self._call_llm(goal, last_errors)
            plan     = self._parse(goal, raw_json)

            if plan is None:
                last_errors = ["Could not parse LLM response as valid JSON."]
                continue

            result: ValidationResult = self._validator.validate(plan)

            if result.valid:
                logger.info(
                    f"Plan created — {len(plan.tasks)} task(s) for: '{goal[:60]}'"
                )
                return plan

            last_errors = result.errors
            logger.warning(
                f"Planner: attempt {attempt} produced invalid plan. "
                f"Errors: {last_errors}"
            )

        # All retries exhausted — return a minimal fallback plan
        logger.error(
            "Planner: all attempts failed. Returning fallback plan."
        )
        return self._fallback_plan(goal)

    # ── Private — LLM interaction ─────────────────────────────────────────────

    def _call_llm(self, goal: str, previous_errors: list[str]) -> str:
        """Ask the LLM to produce a JSON plan for the goal."""
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
        """Build the planning prompt, optionally including prior validation errors."""
        tool_list = ", ".join(sorted(self._known_tools)) or "none"

        error_section = ""
        if previous_errors:
            error_lines  = "\n".join(f"  - {e}" for e in previous_errors)
            error_section = (
                f"\nYour previous plan was rejected for these reasons:\n"
                f"{error_lines}\n"
                f"Please fix these issues in your new plan.\n"
            )

        return f"""You are a task planning assistant for IRIS, an AI agent.

Break the following goal into a sequence of concrete tasks.
{error_section}
Goal: {goal}

Available tools: {tool_list}

Rules:
- Return ONLY a JSON object — no explanation, no markdown, no code fences.
- Each task must have: id (integer), description (string), tool (string or null), dependencies (list of ints).
- Use "tool": null for reasoning or planning steps that need no tool.
- Use "tool": "llm" for steps that require language generation.
- task IDs must be unique integers starting at 1.
- List dependencies as IDs of tasks that must finish before this one.
- Keep the plan concise: 3–8 tasks for most goals.

Required JSON format:
{{
  "goal": "{goal}",
  "tasks": [
    {{"id": 1, "description": "First step", "tool": null, "dependencies": []}},
    {{"id": 2, "description": "Second step", "tool": "file_reader", "dependencies": [1]}}
  ]
}}"""

    # ── Private — parsing ─────────────────────────────────────────────────────

    @staticmethod
    def _parse(goal: str, raw: str) -> Plan | None:
        """
        Extract and parse the JSON object from the LLM response.
        Handles responses wrapped in markdown code fences.
        Returns None on any parse failure.
        """
        if not raw:
            return None

        # Strip markdown fences if present: ```json ... ```
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # Extract the first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.warning("Planner: no JSON object found in LLM response.")
            return None

        try:
            data  = json.loads(match.group())
            tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
            return Plan(goal=goal, tasks=tasks)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Planner: JSON parse error: {e}")
            return None

    # ── Private — fallback ────────────────────────────────────────────────────

    @staticmethod
    def _fallback_plan(goal: str) -> Plan:
        """
        Return a minimal two-task plan used when all LLM attempts fail.
        Ensures the workflow always has something to execute.
        """
        return Plan(
            goal  = goal,
            tasks = [
                Task(id=1, description="Understand the user's request", tool=None),
                Task(id=2, description="Generate a response with the LLM",
                     tool="llm", dependencies=[1]),
            ],
        )
