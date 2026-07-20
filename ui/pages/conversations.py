"""
ui/pages/conversations.py

Dedicated Conversations page — browse, manage, import, export all chats.
"""

from __future__ import annotations

import json

import streamlit as st

from ui.components.conversation_list import render_conversation_list
from ui.components.export_chat       import render_export_buttons
from ui.utils.session import (
    new_conv,
    list_conversations,
    _active_conv_id,
    _now,
    _all_conversations,
)


def render() -> None:
    st.markdown("## 💬 Conversations")
    st.markdown(
        '<p style="color:#8b949e;">Manage all your IRIS conversations.</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Top bar ───────────────────────────────────────────────────────────────
    col_new, col_search, col_spacer = st.columns([2, 5, 3])

    with col_new:
        if st.button("＋ New conversation", key="conv_page_new",
                     type="primary", use_container_width=True):
            new_conv()
            st.rerun()

    with col_search:
        search = st.text_input(
            "Search",
            placeholder="Search by name or content...",
            key="conv_page_search",
            label_visibility="collapsed",
        )

    # ── Import ────────────────────────────────────────────────────────────────
    with st.expander("⬆️ Import conversation from JSON"):
        uploaded = st.file_uploader(
            "Upload JSON",
            type=["json"],
            key="conv_import_upload",
            label_visibility="collapsed",
        )
        if uploaded:
            try:
                data = json.loads(uploaded.read().decode("utf-8"))
                _do_import(data)
                st.success("Conversation imported successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Import failed: {exc}")

    st.divider()

    # ── Conversation list ─────────────────────────────────────────────────────
    render_conversation_list(search_query=search, show_actions=True)

    st.divider()

    # ── Bulk export ───────────────────────────────────────────────────────────
    st.markdown("**Export active conversation**")
    active_convs = list_conversations()
    if active_convs:
        active_id = _active_conv_id()
        active    = next((c for c in active_convs if c["id"] == active_id), active_convs[0])
        render_export_buttons(active["messages"], active["name"])

    # ── Bulk delete ───────────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Danger zone**")
    if st.button("🗑️ Delete ALL conversations", key="conv_del_all"):
        st.session_state["conv_confirm_all"] = True

    if st.session_state.get("conv_confirm_all"):
        st.warning("This will permanently delete every conversation.")
        cy, cn = st.columns(2)
        if cy.button("Confirm delete all", key="conv_del_all_yes"):
            st.session_state.pop("conversations", None)
            st.session_state.pop("active_conv_id", None)
            st.session_state.pop("conv_confirm_all", None)
            new_conv()
            st.success("All conversations deleted.")
            st.rerun()
        if cn.button("Cancel", key="conv_del_all_no"):
            st.session_state.pop("conv_confirm_all", None)
            st.rerun()


def _do_import(data: dict) -> None:
    import uuid
    conv_id = str(uuid.uuid4())
    convs   = _all_conversations()
    convs[conv_id] = {
        "id":       conv_id,
        "name":     data.get("name", "Imported Chat"),
        "messages": data.get("messages", []),
        "created":  data.get("created", _now()),
        "pinned":   False,
    }
    st.session_state["active_conv_id"] = conv_id
