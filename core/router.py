"""
core/router.py

Routes a user query to a tool or falls through to the LLM.
Depends on Reasoner and ToolManager, both injected via the Container.
"""

from app.container import Container
from utils.logger import logger


class Router:
    """
    Directs a user query to the appropriate handler.

    Returns (result, handled):
      - handled=True  → a tool processed the query; result holds the output
      - handled=False → no tool matched; caller should fall through to the LLM
    """

    def __init__(self, container: Container) -> None:
        self.reasoner = container.reasoner
        self.tool_manager = container.tool_manager

    def process(self, query: str) -> tuple[str, bool]:
        """Analyze the query and route it to a tool or signal LLM fallback."""
        action: str = self.reasoner.analyze(query)
        logger.debug(f"Router: action={action} for query='{query}'")

        if action == "llm":
            return query, False

        result = self.tool_manager.execute(query)
        return result, True
