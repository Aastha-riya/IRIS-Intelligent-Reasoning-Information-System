"""
ui/components/message.py

Chat message renderer — styled user and IRIS bubbles with decision badges.
"""

import streamlit as st


_BADGE_CLASS = {
    "direct":  "badge-direct",
    "tool":    "badge-tool",
    "plan":    "badge-plan",
    "clarify": "badge-clarify",
    "":        "",
}

_BADGE_LABEL = {
    "direct":  "⚡ Direct",
    "tool":    "🔧 Tool",
    "plan":    "📋 Plan",
    "clarify": "❓ Clarify",
    "":        "",
}


def render_message(role: str, content: str, decision: str = "") -> None:
    """
    Render a single chat message bubble.

    Args:
        role:     "user" or "assistant"
        content:  Message text (may contain markdown)
        decision: Agent decision type for assistant messages
    """
    if role == "user":
        st.markdown(
            f'<div class="user-bubble">{content}</div>',
            unsafe_allow_html=True,
        )
    else:
        badge_html = ""
        if decision and decision in _BADGE_CLASS and _BADGE_CLASS[decision]:
            badge_html = (
                f'<div class="decision-badge {_BADGE_CLASS[decision]}">'
                f'{_BADGE_LABEL[decision]}</div>'
            )

        # Render content as markdown inside the bubble
        # Using a container lets us mix HTML wrapper + st.markdown
        with st.container():
            st.markdown(
                f'<div class="iris-bubble">{badge_html}',
                unsafe_allow_html=True,
            )
            st.markdown(content)
            st.markdown("</div>", unsafe_allow_html=True)


def render_history(history: list[dict]) -> None:
    """Render all messages in the chat history."""
    for msg in history:
        render_message(
            role     = msg["role"],
            content  = msg["content"],
            decision = msg.get("decision", ""),
        )
