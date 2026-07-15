"""
tests/test_context_builder.py

Unit tests for memory/context_builder.py (ContextBuilder).

No LLM, no embeddings, no FAISS — pure unit tests using mock data.

Run with:
    python -m pytest tests/test_context_builder.py -v

Test cases:
    1.  Full input (query + history + memories) — output contains all 4 sections.
    2.  No memories → still builds a valid prompt (system + history + question).
    3.  Empty history → still builds a valid prompt (system + memories + question).
    4.  Both empty → minimal valid prompt (system + question only).
    5.  Output always ends with the current user question.
    6.  Output always starts with the system prompt.
    7.  Memory section appears before history in the message list.
    8.  Memories capped to MAX_CONTEXT_MEMORIES.
    9.  History capped to MAX_CONTEXT_HISTORY messages.
    10. Exact duplicate memories are deduplicated.
    11. Substring duplicate memories are deduplicated.
    12. Token budget: oversized history is trimmed, system + question preserved.
    13. Memory content appears in the assembled messages.
    14. History content appears in the assembled messages.
"""

import pytest

from memory.context_builder import ContextBuilder, _estimate_tokens
from memory.retriever import RetrievedMemory
from config.settings import (
    MAX_CONTEXT_MEMORIES,
    MAX_CONTEXT_HISTORY,
    CONTEXT_TOKEN_BUDGET,
    SYSTEM_PROMPT,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_memory(text: str, score: float = 0.9) -> RetrievedMemory:
    return RetrievedMemory(
        text=text,
        similarity_score=score,
        timestamp="2026-07-14 10:00:00",
        importance=1.0,
        rank_score=score,
    )


def _make_history(n_turns: int) -> list[dict]:
    """Create n_turns of flat user/assistant message pairs."""
    messages = []
    for i in range(n_turns):
        messages.append({"role": "user",      "content": f"User message {i}"})
        messages.append({"role": "assistant",  "content": f"Assistant reply {i}"})
    return messages


def _get_roles(messages: list[dict]) -> list[str]:
    return [m["role"] for m in messages]


def _all_content(messages: list[dict]) -> str:
    return "\n".join(m["content"] for m in messages)


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def builder() -> ContextBuilder:
    return ContextBuilder()


# ── Test 1: Full input produces all four sections ─────────────────────────────

def test_full_input_contains_all_sections(builder: ContextBuilder) -> None:
    memories = [_make_memory("User prefers Java.")]
    history  = _make_history(2)
    query    = "What language do I prefer?"

    messages = builder.build(query, history, memories)

    content = _all_content(messages)
    assert SYSTEM_PROMPT.strip()[:30] in content,  "System prompt missing."
    assert "Java"                      in content,  "Memory content missing."
    assert "User message 0"            in content,  "History missing."
    assert query                       in content,  "User question missing."


# ── Test 2: No memories → valid prompt ───────────────────────────────────────

def test_no_memories_builds_valid_prompt(builder: ContextBuilder) -> None:
    history  = _make_history(2)
    messages = builder.build("Hello?", history, [])

    assert len(messages) >= 2, "Must have at least system prompt + question."
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Hello?"


# ── Test 3: Empty history → valid prompt ─────────────────────────────────────

def test_empty_history_builds_valid_prompt(builder: ContextBuilder) -> None:
    memories = [_make_memory("I use VS Code.")]
    messages = builder.build("What editor do I use?", [], memories)

    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "What editor do I use?"
    assert any("VS Code" in m["content"] for m in messages)


# ── Test 4: Both empty → minimal valid prompt ─────────────────────────────────

def test_both_empty_builds_minimal_prompt(builder: ContextBuilder) -> None:
    messages = builder.build("How are you?", [], [])

    roles = _get_roles(messages)
    assert roles[0]  == "system", "First message must be system prompt."
    assert roles[-1] == "user",   "Last message must be user question."
    assert messages[-1]["content"] == "How are you?"


# ── Test 5: Output always ends with current user question ─────────────────────

def test_output_ends_with_user_question(builder: ContextBuilder) -> None:
    query    = "Which language should I learn next?"
    messages = builder.build(query, _make_history(3), [_make_memory("I know Python.")])

    assert messages[-1]["role"]    == "user"
    assert messages[-1]["content"] == query


# ── Test 6: Output always starts with system prompt ──────────────────────────

def test_output_starts_with_system_prompt(builder: ContextBuilder) -> None:
    messages = builder.build("Hi", _make_history(1), [])

    assert messages[0]["role"] == "system"
    assert SYSTEM_PROMPT.strip()[:20] in messages[0]["content"]


# ── Test 7: Memory section appears before history ────────────────────────────

def test_memory_section_before_history(builder: ContextBuilder) -> None:
    memories = [_make_memory("User is in B.Tech AIML.")]
    history  = _make_history(1)   # user message 0, assistant reply 0
    messages = builder.build("Tell me about myself.", history, memories)

    memory_idx  = next(i for i, m in enumerate(messages)
                       if "B.Tech" in m["content"])
    history_idx = next(i for i, m in enumerate(messages)
                       if "User message 0" in m["content"])

    assert memory_idx < history_idx, "Memory block must come before history."


# ── Test 8: Memories capped to MAX_CONTEXT_MEMORIES ──────────────────────────

def test_memories_capped(builder: ContextBuilder) -> None:
    many_memories = [_make_memory(f"Fact number {i}.") for i in range(20)]
    messages = builder.build("Tell me everything.", [], many_memories)

    memory_block = next(
        (m for m in messages if m["role"] == "system"
         and "memories" in m["content"].lower()),
        None,
    )
    assert memory_block is not None, "Memory block should exist."

    # Count bullet points — one per injected memory
    bullets = [line for line in memory_block["content"].split("\n") if line.startswith("- ")]
    assert len(bullets) <= MAX_CONTEXT_MEMORIES, (
        f"Should inject at most {MAX_CONTEXT_MEMORIES} memories, got {len(bullets)}."
    )


# ── Test 9: History capped to MAX_CONTEXT_HISTORY messages ───────────────────

def test_history_capped(builder: ContextBuilder) -> None:
    long_history = _make_history(50)   # 100 messages
    messages     = builder.build("What's new?", long_history, [])

    history_messages = [m for m in messages if m["role"] in ("user", "assistant")
                        and m["content"] != "What's new?"]

    assert len(history_messages) <= MAX_CONTEXT_HISTORY * 2, (
        f"History should be capped to {MAX_CONTEXT_HISTORY * 2} messages."
    )


# ── Test 10: Exact duplicate memories deduplicated ────────────────────────────

def test_exact_duplicate_memories_removed(builder: ContextBuilder) -> None:
    memories = [
        _make_memory("User likes Java."),
        _make_memory("User likes Java."),   # exact duplicate
        _make_memory("User likes Java."),   # exact duplicate
    ]
    messages = builder.build("What do I like?", [], memories)

    memory_block = next(
        (m for m in messages if "Java" in m["content"] and m["role"] == "system"
         and "memories" in m["content"].lower()),
        None,
    )
    assert memory_block is not None
    bullets = [l for l in memory_block["content"].split("\n") if l.startswith("- ")]
    assert len(bullets) == 1, f"Duplicates should be removed, got {len(bullets)} bullets."


# ── Test 11: Substring duplicate memories deduplicated ────────────────────────

def test_substring_duplicate_memories_removed(builder: ContextBuilder) -> None:
    memories = [
        _make_memory("User prefers Java over Python."),   # most specific
        _make_memory("User prefers Java."),                # substring of above
    ]
    messages = builder.build("Languages?", [], memories)

    memory_block = next(
        (m for m in messages if "Java" in m["content"] and m["role"] == "system"
         and "memories" in m["content"].lower()),
        None,
    )
    assert memory_block is not None
    bullets = [l for l in memory_block["content"].split("\n") if l.startswith("- ")]
    assert len(bullets) == 1, (
        f"Substring duplicate should be removed, got {len(bullets)} bullets."
    )


# ── Test 12: Token budget trims history, preserves system + question ──────────

def test_token_budget_trims_history(builder: ContextBuilder) -> None:
    # Build a history so large it must exceed the token budget
    huge_history = []
    long_text    = "x" * 500
    for _ in range(100):
        huge_history.append({"role": "user",      "content": long_text})
        huge_history.append({"role": "assistant",  "content": long_text})

    query    = "Final question?"
    messages = builder.build(query, huge_history, [])

    # System prompt must be present
    assert messages[0]["role"] == "system"
    # User question must be last
    assert messages[-1]["content"] == query
    # Total estimated tokens should be within budget (with some tolerance)
    total_chars = sum(len(m["content"]) for m in messages)
    estimated   = total_chars // 4
    assert estimated <= CONTEXT_TOKEN_BUDGET * 1.2, (
        f"After trimming, estimated tokens ({estimated}) should be near budget "
        f"({CONTEXT_TOKEN_BUDGET})."
    )


# ── Test 13: Memory content appears in assembled messages ─────────────────────

def test_memory_content_in_messages(builder: ContextBuilder) -> None:
    memories = [_make_memory("IRIS is preparing for DRDO internship.")]
    messages = builder.build("What am I preparing for?", [], memories)
    content  = _all_content(messages)
    assert "DRDO" in content, "Memory text should appear in assembled messages."


# ── Test 14: History content appears in assembled messages ────────────────────

def test_history_content_in_messages(builder: ContextBuilder) -> None:
    history  = [
        {"role": "user",      "content": "I am studying machine learning."},
        {"role": "assistant",  "content": "That is great!"},
    ]
    messages = builder.build("What am I studying?", history, [])
    content  = _all_content(messages)
    assert "machine learning" in content, "History text should appear in assembled messages."
