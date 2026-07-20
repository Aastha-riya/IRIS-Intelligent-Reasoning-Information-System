"""
ui/components/streaming_chat.py

Streaming response renderer for IRIS.

agent.run() is synchronous — it returns the full response at once.
We simulate a streaming UX by yielding the response word-by-word
through st.write_stream(), so the user sees text appearing
progressively rather than a blank wait followed by a wall of text.

Usage:
    response_text = stream_response(result.output)
    # response_text is the full string after streaming completes

For actual token streaming (future):
    Replace _word_stream() with a generator that yields tokens from
    an async Ollama call.
"""

from __future__ import annotations

import time
from typing import Generator

import streamlit as st


# ── Streaming speed ───────────────────────────────────────────────────────────

WORD_DELAY_SECONDS: float = 0.025   # delay between words — feels natural at ~40 wps


# ── Public API ────────────────────────────────────────────────────────────────

def stream_response(text: str, delay: float = WORD_DELAY_SECONDS) -> str:
    """
    Stream a response word-by-word inside a native assistant chat bubble.

    Args:
        text:  Full response text from the agent.
        delay: Seconds between each word.

    Returns:
        The full response text (same as input — useful for saving to history).
    """
    if not text:
        return ""

    with st.chat_message("assistant", avatar="🤖"):
        st.write_stream(_word_stream(text, delay))

    return text


def stream_response_in_container(
    container,
    text:  str,
    delay: float = WORD_DELAY_SECONDS,
) -> str:
    """
    Stream into an existing st.empty() or container slot.
    Used when you need to control exactly where streaming appears.

    Args:
        container: A Streamlit container (st.empty(), st.container(), etc.)
        text:      Full response text.
        delay:     Seconds between words.

    Returns:
        Full response text.
    """
    if not text:
        return ""
    with container:
        st.write_stream(_word_stream(text, delay))
    return text


# ── Private — word generator ──────────────────────────────────────────────────

def _word_stream(text: str, delay: float) -> Generator[str, None, None]:
    """
    Yield words one at a time with a small delay between each.
    Preserves newlines so code blocks and lists format correctly.
    """
    # Split by spaces while keeping newlines intact
    tokens = text.split(" ")
    for i, token in enumerate(tokens):
        yield token + (" " if i < len(tokens) - 1 else "")
        time.sleep(delay)
