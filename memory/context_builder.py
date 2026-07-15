"""
memory/context_builder.py

The brain before the LLM — builds the best possible prompt every turn.

Single responsibility:
    inputs  →  one complete, structured message list for the LLM

Nothing else.  No embeddings.  No FAISS.  No tool execution.  No storage.

Professional AI systems never send raw history to the LLM.
Instead they build a carefully structured prompt in four sections:

    ┌─────────────────────────────────────────┐
    │  SECTION 1 — SYSTEM PROMPT              │
    │  Who IRIS is and how it behaves         │
    ├─────────────────────────────────────────┤
    │  SECTION 2 — RELEVANT MEMORIES          │
    │  Semantically retrieved past context    │
    │  (ranked, deduplicated, capped)         │
    ├─────────────────────────────────────────┤
    │  SECTION 3 — RECENT CONVERSATION        │
    │  Last N message turns                   │
    ├─────────────────────────────────────────┤
    │  SECTION 4 — CURRENT QUESTION           │
    │  The user's message this turn           │
    └─────────────────────────────────────────┘

This is how ChatGPT, Claude, Cursor, and production RAG systems work.

Inputs  (provided by MemoryManager):
    user_query:        str                    — current user message
    recent_history:    list[{role, content}]  — from ConversationHistory.recent()
    relevant_memories: list[RetrievedMemory]  — ranked results from Retriever

Output:
    list[{role, content}]  — ready for ollama.chat(messages=...)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.settings import (
    CONTEXT_TOKEN_BUDGET,
    MAX_CONTEXT_HISTORY,
    MAX_CONTEXT_MEMORIES,
    SYSTEM_PROMPT,
)
from utils.logger import logger

if TYPE_CHECKING:
    from memory.retriever import RetrievedMemory

# Rough token estimator: average English word ≈ 1.3 tokens; 1 char ≈ 0.25 tokens
_CHARS_PER_TOKEN: float = 4.0


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length (fast approximation)."""
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


class ContextBuilder:
    """
    Assembles the structured message list sent to the LLM each turn.

    Pipeline:
        1. Start with the system prompt (always included, never trimmed)
        2. Deduplicate memories — drop near-duplicate texts before injecting
        3. Cap memories to MAX_CONTEXT_MEMORIES
        4. Cap history to the last MAX_CONTEXT_HISTORY messages
        5. Trim history further if the token budget is exceeded
        6. Append the current user question
    """

    # Deduplication: two memory texts are "duplicates" if one is a substring
    # of the other (case-insensitive, stripped). Exact string match is also caught.
    _DEDUP_SIMILARITY: float = 0.85   # reserved for future fuzzy dedup

    def __init__(self) -> None:
        self._system_message: dict = {
            "role":    "system",
            "content": SYSTEM_PROMPT.strip(),
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def build(
        self,
        user_query: str,
        recent_history: list[dict],
        relevant_memories: list[RetrievedMemory],
    ) -> list[dict]:
        """
        Build the complete four-section message list for an LLM call.

        Args:
            user_query:        The current user input string.
            recent_history:    Flat [{role, content}] messages from
                               ConversationHistory.recent().
            relevant_memories: RetrievedMemory objects from Retriever,
                               already ranked best-first.

        Returns:
            Ordered list of {role, content} dicts ready for ollama.chat().
        """
        logger.info("Building prompt...")

        messages: list[dict] = []

        # ── Section 1: System prompt ──────────────────────────────────────────
        messages.append(self._system_message)

        # ── Section 2: Relevant memories ─────────────────────────────────────
        memory_block = self._build_memory_section(relevant_memories)
        if memory_block:
            messages.append(memory_block)

        # ── Section 3: Recent conversation ───────────────────────────────────
        history_messages = self._build_history_section(recent_history)
        messages.extend(history_messages)
        logger.info(f"Added {len(history_messages)} chat messages.")

        # ── Section 4: Current user question ─────────────────────────────────
        messages.append({"role": "user", "content": user_query})

        # ── Token budget guard ────────────────────────────────────────────────
        messages = self._apply_token_budget(messages)

        logger.info("Final prompt ready.")
        logger.debug(
            f"ContextBuilder summary — "
            f"memories: {len(relevant_memories)}, "
            f"history messages: {len(history_messages)}, "
            f"total blocks: {len(messages)}, "
            f"~{self._total_tokens(messages)} tokens."
        )
        return messages

    # ── Private — section builders ────────────────────────────────────────────

    def _build_memory_section(
        self,
        memories: list[RetrievedMemory],
    ) -> dict | None:
        """
        Deduplicate, cap, and format memories into a single system message.
        Returns None if there are no memories to inject.
        """
        if not memories:
            return None

        # Deduplicate
        unique = self._deduplicate(memories)
        capped = unique[:MAX_CONTEXT_MEMORIES]

        memory_lines = "\n".join(f"- {m.text}" for m in capped)
        logger.info(f"Added {len(capped)} memories.")

        return {
            "role": "system",
            "content": (
                "Relevant memories from past conversations:\n"
                + memory_lines
            ),
        }

    def _build_history_section(
        self,
        recent_history: list[dict],
    ) -> list[dict]:
        """
        Cap history to the last MAX_CONTEXT_HISTORY messages.
        Each conversation turn = 2 messages (user + assistant).
        """
        # MAX_CONTEXT_HISTORY is in turns; multiply by 2 for message count
        limit = MAX_CONTEXT_HISTORY * 2
        return recent_history[-limit:] if recent_history else []

    # ── Private — deduplication ───────────────────────────────────────────────

    @staticmethod
    def _deduplicate(
        memories: list[RetrievedMemory],
    ) -> list[RetrievedMemory]:
        """
        Remove near-duplicate memories.

        Deduplication rules (applied in order, best-ranked memory wins):
        1. Exact text match (case-insensitive, stripped) — drop the duplicate.
        2. Substring containment — if memory A's text contains memory B's text
           entirely, drop B (A already conveys B's information).

        The list is already ranked best-first by Retriever, so the first
        occurrence of any content is always kept.
        """
        seen:   list[str] = []    # normalised texts of kept memories
        unique: list[RetrievedMemory] = []

        for memory in memories:
            normalised = memory.text.strip().lower()

            # Rule 1: exact duplicate
            if normalised in seen:
                logger.debug(f"ContextBuilder: dedup — exact match dropped: '{memory.text[:50]}'")
                continue

            # Rule 2: substring — this memory's text is already contained in a kept one
            if any(normalised in kept or kept in normalised for kept in seen):
                logger.debug(f"ContextBuilder: dedup — substring match dropped: '{memory.text[:50]}'")
                continue

            seen.append(normalised)
            unique.append(memory)

        if len(unique) < len(memories):
            logger.debug(
                f"ContextBuilder: dedup removed "
                f"{len(memories) - len(unique)} duplicate(s)."
            )
        return unique

    # ── Private — token budget ────────────────────────────────────────────────

    def _apply_token_budget(self, messages: list[dict]) -> list[dict]:
        """
        Trim the oldest history messages if the estimated token count
        exceeds CONTEXT_TOKEN_BUDGET.

        Never trims: system messages or the final user message.
        Trims from: the oldest history messages first (least relevant).
        """
        total = self._total_tokens(messages)
        if total <= CONTEXT_TOKEN_BUDGET:
            return messages

        logger.warning(
            f"ContextBuilder: estimated {total} tokens exceeds budget "
            f"({CONTEXT_TOKEN_BUDGET}). Trimming history."
        )

        # Separate fixed messages (system blocks + last user msg) from trimmable history
        system_messages = [m for m in messages if m["role"] == "system"]
        user_assistant  = [m for m in messages if m["role"] != "system"]

        # The last element is always the current user question — keep it
        current_question = user_assistant[-1] if user_assistant else None
        history          = user_assistant[:-1] if len(user_assistant) > 1 else []

        # Drop oldest history messages two at a time (one turn = user + assistant)
        while history and self._total_tokens(
            system_messages + history + ([current_question] if current_question else [])
        ) > CONTEXT_TOKEN_BUDGET:
            history = history[2:]   # drop oldest turn (user + assistant pair)

        trimmed = system_messages + history
        if current_question:
            trimmed.append(current_question)

        logger.debug(
            f"ContextBuilder: trimmed to ~{self._total_tokens(trimmed)} tokens."
        )
        return trimmed

    @staticmethod
    def _total_tokens(messages: list[dict]) -> int:
        """Estimate total token count for a list of messages."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return _estimate_tokens(str(total_chars))
