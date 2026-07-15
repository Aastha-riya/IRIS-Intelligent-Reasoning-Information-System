"""
memory/summarizer.py

Compresses older conversation turns into a short summary string.
Prevents the history file from growing unbounded and keeps
the context window lean.

Planned pipeline:
    Old turns (beyond MAX_HISTORY)
        ↓
    LLM summarization call
        ↓
    Single summary paragraph
        ↓
    Saved to summary.json
        ↓
    Injected into ContextBuilder as background knowledge

Currently a stub — the interface is defined so MemoryManager
can call it without changes once the implementation lands.
"""

from utils.logger import logger


class Summarizer:
    """
    Summarizes older conversation turns to keep the prompt compact.
    Requires an LLM reference to generate the summary — injected at construction
    to avoid circular imports (LLM → MemoryManager → Summarizer → LLM).
    """

    def __init__(self) -> None:
        # LLM will be wired in once the summarization call is implemented
        self._llm = None
        logger.debug("Summarizer initialized (implementation pending).")

    def set_llm(self, llm) -> None:
        """
        Inject the LLM dependency after construction to break the
        circular dependency with MemoryManager.
        """
        self._llm = llm

    def summarize(self, turns: list[dict]) -> str:
        """
        (Planned) Summarize a list of conversation turns into a
        single compact paragraph.

        Args:
            turns: List of {user, assistant, time} dicts.

        Returns:
            A summary string, or empty string if not yet implemented.
        """
        if not self._llm:
            logger.debug("Summarizer.summarize: LLM not wired yet — skipping.")
            return ""

        # TODO: build a summarization prompt and call self._llm.chat()
        logger.debug("Summarizer.summarize: not yet implemented.")
        return ""
