"""
tools/base_tool.py

Abstract base class for all IRIS tools.
Every tool must implement can_handle() and execute().
"""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """
    Contract that every tool must satisfy.

    Subclasses define:
      - name: unique tool identifier string
      - description: human-readable purpose
      - can_handle(): returns True if this tool should process the query
      - execute(): runs the tool and returns a result string
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def can_handle(self, query: str) -> bool:
        """Return True if this tool can process the given query."""

    @abstractmethod
    def execute(self, query: str) -> str:
        """Execute the tool logic and return the result as a string."""
