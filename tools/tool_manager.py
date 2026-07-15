"""
tools/tool_manager.py

Registry of all available tools.
Iterates tools to find one that can handle a query, then executes it.
"""

from tools.calculator import Calculator
from tools.file_reader import FileReader
from tools.project_scanner import ProjectScanner
from utils.logger import logger

# from tools.internet import Internet   # uncomment when re-enabled


class ToolManager:
    """
    Manages all registered tools and routes queries to the correct one.
    To add a new tool: instantiate it in __init__ and add it to self.tools.
    """

    def __init__(self) -> None:
        self.tools: dict = {
            "calculator":     Calculator(),
            "file_reader":    FileReader(),
            "project_scanner": ProjectScanner(),
        }
        logger.debug(f"ToolManager registered tools: {list(self.tools.keys())}")

    def execute(self, query: str) -> str | None:
        """
        Find the first tool that can handle the query and run it.
        Returns the tool result string, or None if no tool matched.
        """
        for name, tool in self.tools.items():
            if tool.can_handle(query):
                logger.info(f"Tool selected: {name}")
                try:
                    result = tool.execute(query)
                    logger.info(f"Tool '{name}' executed successfully.")
                    return result
                except Exception as e:
                    logger.exception(f"Tool '{name}' failed: {e}")
                    return f"Tool error: {e}"

        logger.debug("No tool matched the query.")
        return None
