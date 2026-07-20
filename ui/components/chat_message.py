"""
ui/components/chat_message.py

Professional chat message renderer using Streamlit's native st.chat_message().

Features:
    - Native chat bubbles (user / assistant avatars)
    - Full markdown rendering (bold, italic, lists, tables)
    - Syntax-highlighted code blocks via st.code()
    - Decision type badge (Direct / Tool / Plan / Clarify)
    - Timestamp display
    - Future-ready for images and file attachments
"""

from __future__ import annotations

import streamlit as st


# ── Decision badge config ─────────────────────────────────────────────────────

_BADGE = {
    "direct":  ("⚡ Direct",   "#79c0ff", "#1f6feb"),
    "tool":    ("🔧 Tool",     "#56d364", "#2ea043"),
    "plan":    ("📋 Plan",     "#e3b341", "#bb8009"),
    "clarify": ("❓ Clarify",  "#d2a8ff", "#6e40c9"),
}


def _decision_badge(decision: str) -> str:
    """Return an HTML badge span for the decision type, or empty string."""
    if decision not in _BADGE:
        return ""
    label, color, border = _BADGE[decision]
    return (
        f'<span style="display:inline-block;font-size:0.68rem;padding:2px 8px;'
        f'border-radius:10px;font-weight:600;letter-spacing:0.04em;'
        f'color:{color};border:1px solid {border};'
        f'background:{border}22;margin-bottom:6px;">{label}</span>'
    )


# ── Public API ────────────────────────────────────────────────────────────────

def render_user_message(content: str, timestamp: str = "") -> None:
    """
    Render a user message in the native Streamlit chat bubble.

    Args:
        content:   Message text (may contain markdown).
        timestamp: Optional ISO-style timestamp string.
    """
    with st.chat_message("user", avatar="🧑"):
        st.markdown(content)
        if timestamp:
            st.markdown(
                f'<div style="font-size:0.7rem;color:#8b949e;'
                f'text-align:right;margin-top:4px;">{timestamp}</div>',
                unsafe_allow_html=True,
            )


def render_assistant_message(
    content:  str,
    decision: str = "",
    timestamp: str = "",
) -> None:
    """
    Render an IRIS assistant message with optional decision badge.

    Handles three content types automatically:
        - Plain text / markdown  → st.markdown()
        - Fenced code blocks     → st.code() with syntax highlighting
        - Mixed content          → split and render each part

    Args:
        content:   Response text (may contain markdown and code fences).
        decision:  Agent decision type ('direct', 'tool', 'plan', 'clarify').
        timestamp: Optional timestamp string.
    """
    with st.chat_message("assistant", avatar="🤖"):
        # Decision badge
        if decision and decision in _BADGE:
            st.markdown(_decision_badge(decision), unsafe_allow_html=True)

        # Smart content rendering
        _render_content(content)

        if timestamp:
            st.markdown(
                f'<div style="font-size:0.7rem;color:#8b949e;'
                f'margin-top:4px;">{timestamp}</div>',
                unsafe_allow_html=True,
            )


def render_message(msg: dict) -> None:
    """
    Render a message dict from session state.

    Args:
        msg: dict with keys: role, content, decision (optional), timestamp (optional)
    """
    role      = msg.get("role", "assistant")
    content   = msg.get("content", "")
    decision  = msg.get("decision", "")
    timestamp = msg.get("timestamp", "")

    if role == "user":
        render_user_message(content, timestamp)
    else:
        render_assistant_message(content, decision, timestamp)


def render_history(messages: list[dict]) -> None:
    """Render the full message history."""
    for msg in messages:
        render_message(msg)


# ── Private — smart content renderer ─────────────────────────────────────────

def _render_content(content: str) -> None:
    """
    Parse and render content, separating code fences from markdown text.
    Each fenced code block is rendered with st.code() for syntax highlighting.
    """
    import re

    # Split on fenced code blocks: ```lang\n...\n```
    pattern = r"```(\w*)\n(.*?)```"
    parts   = re.split(pattern, content, flags=re.DOTALL)

    if len(parts) == 1:
        # No code blocks — render as plain markdown
        st.markdown(content)
        return

    # Interleaved: [text, lang, code, text, lang, code, ...]
    i = 0
    while i < len(parts):
        text = parts[i].strip()
        if text:
            st.markdown(text)
        i += 1

        if i < len(parts):
            lang = parts[i] or "text"
            i += 1

        if i < len(parts):
            code = parts[i]
            st.code(code, language=lang)
            i += 1
