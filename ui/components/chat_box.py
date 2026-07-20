"""
ui/components/chat_box.py

Chat input + send button component.
Returns the submitted user message, or empty string if nothing was submitted.
"""

import streamlit as st


def render_chat_input(key: str = "chat_input") -> str:
    """
    Render a text input + Send button row.
    Returns the message when submitted, empty string otherwise.
    """
    col_input, col_btn = st.columns([9, 1])

    with col_input:
        user_input = st.text_input(
            label        = "Message",
            placeholder  = "Ask IRIS anything...",
            key          = key,
            label_visibility = "collapsed",
        )

    with col_btn:
        send = st.button("➤", key=f"{key}_send", use_container_width=True)

    # Submit on Enter (text_input) OR clicking Send
    if send and user_input.strip():
        return user_input.strip()
    return ""
