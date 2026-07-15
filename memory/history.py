"""
memory/history.py

Conversation history model and management.
Single responsibility: represent and manage the ordered list of chat turns.

A turn is stored as:
    {
        "user":      "Hello",
        "assistant": "Hi! How can I help?",
        "time":      "2026-07-14 21:10:05"
    }
"""

from datetime import datetime

from config.settings import MAX_HISTORY
from utils.logger import logger


class ConversationHistory:
    """
    Manages an in-memory list of conversation turns.
    Persisting to disk is handled by Storage — this class only
    models and shapes the data.
    """

    def __init__(self, raw: list[dict]) -> None:
        """
        Initialise from raw stored data (list of turn dicts).
        Accepts both the old flat {role, content} format and the
        new {user, assistant, time} turn format so existing
        history files continue to work.
        """
        self._turns: list[dict] = self._normalise(raw)

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, user: str, assistant: str) -> dict:
        """
        Record a completed exchange and return the turn dict.
        The turn is appended to the in-memory list.
        """
        turn = {
            "user": user,
            "assistant": assistant,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._turns.append(turn)
        logger.debug(f"History: turn recorded at {turn['time']}")
        return turn

    def recent(self, n: int = MAX_HISTORY) -> list[dict]:
        """
        Return the last n turns as a flat list of Ollama-style
        {role, content} message dicts, ready to pass to the LLM.
        """
        recent_turns = self._turns[-n:]
        messages: list[dict] = []
        for turn in recent_turns:
            messages.append({"role": "user",      "content": turn["user"]})
            messages.append({"role": "assistant",  "content": turn["assistant"]})
        logger.debug(f"History: returning {len(messages)} messages ({len(recent_turns)} turns).")
        return messages

    def all_turns(self) -> list[dict]:
        """Return all stored turns in their native format."""
        return list(self._turns)

    def clear(self) -> None:
        """Remove all turns from the in-memory list."""
        self._turns.clear()
        logger.debug("History: cleared.")

    def __len__(self) -> int:
        return len(self._turns)

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(raw: list[dict]) -> list[dict]:
        """
        Convert legacy flat {role, content} records into turn dicts.
        New-format records (with 'user' key) are passed through unchanged.
        Legacy records are paired up (user msg followed by assistant msg).
        """
        if not raw:
            return []

        # Already new format
        if raw and "user" in raw[0]:
            return raw

        # Legacy format: flat list of {role, content}
        turns: list[dict] = []
        i = 0
        while i < len(raw) - 1:
            if raw[i].get("role") == "user" and raw[i + 1].get("role") == "assistant":
                turns.append({
                    "user":      raw[i]["content"],
                    "assistant": raw[i + 1]["content"],
                    "time":      "migrated",
                })
                i += 2
            else:
                i += 1
        return turns
