"""
brain/validator.py

Plan validator — checks a Plan for structural problems before execution.

Single responsibility:
    Plan  →  ValidationResult (valid=True/False + list of error messages)

Checks performed:
    1. At least one task exists.
    2. No duplicate task IDs.
    3. Every task has a non-empty description.
    4. All dependency IDs reference tasks that exist in the plan.
    5. No circular dependencies (topological sort).
    6. All tool names are known to ToolManager (or are None / "llm").

Nothing is executed here. Nothing is stored. No LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.plan import Plan
from models.task import Task
from utils.logger import logger

# Tools that are always valid regardless of what ToolManager knows
_BUILTIN_TOOLS: frozenset[str] = frozenset({"llm", "none"})


@dataclass
class ValidationResult:
    """Outcome of a plan validation run."""
    valid:  bool
    errors: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def __str__(self) -> str:
        if self.valid:
            return "Plan is valid."
        return "Plan is INVALID:\n" + "\n".join(f"  - {e}" for e in self.errors)


class PlanValidator:
    """
    Validates a Plan before the Workflow executes it.
    Injected with the set of known tool names from ToolManager.
    """

    def __init__(self, known_tools: set[str]) -> None:
        """
        Args:
            known_tools: Tool names registered in ToolManager
                         (e.g. {"calculator", "file_reader", "project_scanner"}).
        """
        self._known_tools: set[str] = known_tools | _BUILTIN_TOOLS

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self, plan: Plan) -> ValidationResult:
        """
        Run all checks on the plan and return a ValidationResult.

        Args:
            plan: The Plan to validate.

        Returns:
            ValidationResult with valid=True if all checks pass,
            or valid=False with a list of human-readable error messages.
        """
        result = ValidationResult(valid=True)

        self._check_has_tasks(plan, result)
        if not result.valid:
            # No point running further checks on an empty plan
            return result

        self._check_duplicate_ids(plan, result)
        self._check_descriptions(plan, result)
        self._check_dependency_references(plan, result)
        self._check_unknown_tools(plan, result)

        if result.valid:
            # Circular dependency check requires valid references
            self._check_circular_dependencies(plan, result)

        if result.valid:
            logger.info("Plan validation passed.")
        else:
            logger.warning(f"Plan validation failed:\n{result}")

        return result

    # ── Private checks ────────────────────────────────────────────────────────

    @staticmethod
    def _check_has_tasks(plan: Plan, result: ValidationResult) -> None:
        if not plan.tasks:
            result.add_error("Plan contains no tasks.")

    @staticmethod
    def _check_duplicate_ids(plan: Plan, result: ValidationResult) -> None:
        seen: set[int] = set()
        for task in plan.tasks:
            if task.id in seen:
                result.add_error(f"Duplicate task ID: {task.id}.")
            seen.add(task.id)

    @staticmethod
    def _check_descriptions(plan: Plan, result: ValidationResult) -> None:
        for task in plan.tasks:
            if not task.description or not task.description.strip():
                result.add_error(f"Task {task.id} has an empty description.")

    @staticmethod
    def _check_dependency_references(plan: Plan, result: ValidationResult) -> None:
        valid_ids = {t.id for t in plan.tasks}
        for task in plan.tasks:
            for dep_id in task.dependencies:
                if dep_id not in valid_ids:
                    result.add_error(
                        f"Task {task.id} depends on unknown task ID {dep_id}."
                    )
                if dep_id == task.id:
                    result.add_error(
                        f"Task {task.id} depends on itself."
                    )

    def _check_unknown_tools(self, plan: Plan, result: ValidationResult) -> None:
        for task in plan.tasks:
            tool = (task.tool or "").strip().lower()
            if tool and tool not in self._known_tools:
                result.add_error(
                    f"Task {task.id} references unknown tool '{task.tool}'. "
                    f"Known tools: {sorted(self._known_tools)}."
                )

    @staticmethod
    def _check_circular_dependencies(plan: Plan, result: ValidationResult) -> None:
        """
        Detect cycles using Kahn's algorithm (topological sort).
        A cycle exists if not all nodes can be processed.
        """
        adj:     dict[int, list[int]] = {t.id: list(t.dependencies) for t in plan.tasks}
        in_deg:  dict[int, int]       = {t.id: len(t.dependencies) for t in plan.tasks}
        queue:   list[int]            = [tid for tid, deg in in_deg.items() if deg == 0]
        visited: int                  = 0

        while queue:
            node = queue.pop(0)
            visited += 1
            for other_id, deps in adj.items():
                if node in deps:
                    in_deg[other_id] -= 1
                    if in_deg[other_id] == 0:
                        queue.append(other_id)

        if visited < len(plan.tasks):
            result.add_error(
                "Plan contains a circular dependency — "
                "one or more tasks form a dependency cycle."
            )
