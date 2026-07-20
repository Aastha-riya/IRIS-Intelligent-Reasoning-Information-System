"""
ui/components/chat_header.py

Chat page header — conversation name, agent status strip, and action buttons.

Shows:
    - Current conversation name (editable inline)
    - Live agent status with animated indicator
    - Current thinking stage when agent is running
    - Action buttons: New Chat, Clear, Rename, Delete
"""

from __future__ import annotations

import streamlit as st

from ui.utils.session import (
    get_agent_status,
    get_active_conv,
    get_thinking_stage,
    new_conv,
    clear_chat,
    rename_conv,
    delete_conv,
    switch_conv,
    _active_conv_id,
)


# ── Status strip config ───────────────────────────────────────────────────────

_STATUS_CONFIG = {
    "idle":    ("⬤", "#56d364", "Ready"),
    "running": ("⬤", "#e3b341", "Running"),
    "paused":  ("⬤", "#8b949e", "Paused"),
    "stopped": ("⬤", "#f85149", "Stopped"),
    "offline": ("⬤", "#f85149", "Offline"),
}


def render_chat_header() -> None:
    """
    Render the chat page header with conversation controls and agent status.
    """
    conv = get_active_conv()

    # ── Top row: name + status + buttons ─────────────────────────────────────
    col_name, col_status, col_new, col_clear, col_rename, col_delete = st.columns(
        [4, 3, 1, 1, 1, 1]
    )

    with col_name:
        st.markdown(
            f'<h3 style="margin:0;padding:4px 0;font-size:1.15rem;">'
            f'💬 {conv["name"]}</h3>',
            unsafe_allow_html=True,
        )

    with col_status:
        agent_status = get_agent_status()
        dot, color, label = _STATUS_CONFIG.get(
            agent_status, ("⬤", "#8b949e", agent_status)
        )
        stage = get_thinking_stage()
        status_text = stage if stage and agent_status == "running" else label
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;'
            f'padding:6px 0;font-size:0.85rem;">'
            f'<span style="color:{color};">{dot}</span>'
            f'<span style="color:#8b949e;">{status_text}</span></div>',
            unsafe_allow_html=True,
        )

    with col_new:
        if st.button("＋", key="hdr_new", help="New conversation",
                     use_container_width=True):
            new_conv()
            st.rerun()

    with col_clear:
        if st.button("🗑", key="hdr_clear", help="Clear messages",
                     use_container_width=True):
            clear_chat()
            st.rerun()

    with col_rename:
        if st.button("✏", key="hdr_rename", help="Rename conversation",
                     use_container_width=True):
            st.session_state["renaming"] = True

    with col_delete:
        if st.button("✕", key="hdr_delete", help="Delete conversation",
                     use_container_width=True):
            st.session_state["confirm_delete"] = True

    # ── Rename inline form ────────────────────────────────────────────────────
    if st.session_state.get("renaming"):
        with st.form("rename_form", clear_on_submit=True):
            new_name = st.text_input(
                "New name",
                value=conv["name"],
                key="rename_input",
            )
            col_ok, col_cancel = st.columns(2)
            submitted = col_ok.form_submit_button("Save")
            cancelled = col_cancel.form_submit_button("Cancel")

        if submitted and new_name.strip():
            rename_conv(_active_conv_id(), new_name)
            st.session_state.pop("renaming", None)
            st.rerun()
        if cancelled:
            st.session_state.pop("renaming", None)
            st.rerun()

    # ── Delete confirmation ───────────────────────────────────────────────────
    if st.session_state.get("confirm_delete"):
        st.warning(
            f"Delete **{conv['name']}**? This cannot be undone.",
            icon="⚠️",
        )
        col_yes, col_no = st.columns(2)
        if col_yes.button("Yes, delete", key="del_yes"):
            conv_id = _active_conv_id()
            delete_conv(conv_id)
            st.session_state.pop("confirm_delete", None)
            st.rerun()
        if col_no.button("Cancel", key="del_no"):
            st.session_state.pop("confirm_delete", None)
            st.rerun()

    st.divider()
