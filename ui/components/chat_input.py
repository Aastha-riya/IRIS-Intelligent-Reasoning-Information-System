"""
ui/components/chat_input.py

Chat input component using Streamlit's native st.chat_input().

st.chat_input() is sticky — it always sits at the bottom of the page,
matches the ChatGPT UX, and automatically disables while the page reruns
(preventing double-submission).

Returns the submitted message string, or None if nothing was submitted.
"""

import streamlit as st


def render_chat_input(
    placeholder: str = "Ask IRIS anything...",
    key:         str = "main_chat_input",
    disabled:    bool = False,
) -> str | None:
    """
    Render the sticky bottom chat input.

    Args:
        placeholder: Hint text shown inside the input.
        key:         Unique Streamlit widget key.
        disabled:    Pass True to grey out the input (e.g. while agent is running).

    Returns:
        The user's message string if submitted, otherwise None.
    """
    prompt = st.chat_input(
        placeholder = placeholder,
        key         = key,
        disabled    = disabled,
    )
    return prompt if prompt and prompt.strip() else None
