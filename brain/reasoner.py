"""
brain/reasoner.py

Keyword-based intent classifier.
Inspects the user query and returns the name of the
tool or handler that should process it.
"""


class Reasoner:
    """Analyzes a user query and decides which handler should process it."""

    MATH_KEYWORDS: tuple = ("+", "-", "*", "/", "calculate")

    def analyze(self, query: str) -> str:
        """
        Return the handler name for the given query.

        Returns one of: 'calculator', 'file_reader',
        'project_scanner', 'internet', 'llm'.
        """
        lowered = query.lower()

        if any(op in lowered for op in self.MATH_KEYWORDS):
            return "calculator"
        if lowered.startswith("read "):
            return "file_reader"
        if lowered.startswith("scan "):
            return "project_scanner"
        if lowered.startswith("search "):
            return "internet"

        return "llm"
