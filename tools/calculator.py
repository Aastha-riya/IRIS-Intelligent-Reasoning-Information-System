"""
tools/calculator.py

Evaluates mathematical expressions from natural language queries.
"""

from tools.base_tool import BaseTool
from utils.logger import logger


class Calculator(BaseTool):
    """Solves mathematical expressions provided in the user query."""

    name: str = "calculator"
    description: str = "Evaluate mathematical expressions."

    KEYWORDS: tuple = ("calculate", "+", "-", "*", "/")

    def can_handle(self, query: str) -> bool:
        """Return True if the query contains math operators or keywords."""
        return any(kw in query.lower() for kw in self.KEYWORDS)

    def execute(self, query: str) -> str:
        """
        Extract and evaluate the mathematical expression in the query.
        Returns the result as a string, or an error message on failure.
        """
        expression = query.lower().replace("calculate", "").strip()
        logger.info(f"Calculator expression: {expression}")

        try:
            result = eval(expression)   # noqa: S307
            logger.info(f"Calculator result: {result}")
            return str(result)

        except ZeroDivisionError:
            logger.error("Calculator failed — division by zero.")
            return "Error: Division by zero."

        except Exception as e:
            logger.exception(f"Calculator failed: {e}")
            return "Invalid expression."
