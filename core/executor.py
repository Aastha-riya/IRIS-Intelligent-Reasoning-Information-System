"""
core/executor.py

Walks through a plan produced by the Planner and marks each step complete.
"""

from utils.logger import logger


class Executor:
    """Executes a structured plan by processing each step in sequence."""

    def execute(self, plan: dict) -> dict:
        """
        Mark every step in the plan as completed and return the updated plan.
        """
        goal: str = plan.get("goal", "unknown")
        logger.info(f"Executing plan for: {goal}")

        for step in plan["steps"]:
            step["status"] = "completed"
            logger.debug(f"Step completed: {step['description']}")

        logger.info("Plan execution complete.")
        return plan
