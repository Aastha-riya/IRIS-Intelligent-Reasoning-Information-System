"""
ui/components/conversation_list.py

Reusable conversation list widget.
Renders a searchable, sortable list of conversations with action buttons.
Used by both the sidebar and the Conversations page.
"""

from __future__ import annotations

import streamlit as st

from ui.utils.session import (
    list_conversations,
    search_conversations,
    switch_conv,
    pin_conv,
    delete_conv,
    rename_conv,
    _active_conv_id,
)


def render_conversation_list(
    search_query: str = "",
    show_actions: bool = True,
    max_items:    int  = 50,
) -> None:
    """
    Render a list of conversations with optional action buttons.

    Args:
        search_query: Filter string (empty = show all).
        show_actions: If True, show pin / rename / delete buttons.
        max_items:    Maximum conversations to display.
    """
    convs     = search_conversations(search_query) if search_query else list_conversations()
    active_id = _active_conv_id()

    if not convs:
        st.markdown(
            '<p style="color:#8b949e;font-size:0.85rem;">No conversations found.</p>',
            unsafe_allow_html=True,
        )
        return

    st.caption(f"{len(convs)} conversation(s)")

    for conv in convs[:max_items]:
        _render_row(conv, active_id, show_actions)


def _render_row(conv: dict, active_id: str, show_actions: bool) -> None:
    is_active = conv["id"] == active_id
    is_pinned = conv.get("pinned", False)
    msgs      = len(conv["messages"])
    border    = "#1f6feb" if is_active else "#30363d"
    pin_icon  = "📌" if is_pinned else "·"

    if show_actions:
        col_info, col_open, col_pin, col_del = st.columns([6, 2, 1, 1])
    else:
        col_info, col_open = st.columns([7, 3])

    with col_info:
        st.markdown(
            f'<div style="border-left:3px solid {border};padding-left:10px;'
            f'padding:6px 0 6px 10px;">'
            f'<strong>{"▶ " if is_active else ""}{conv["name"][:30]}</strong> '
            f'<span style="color:#8b949e;font-size:0.75rem;">'
            f'{pin_icon} {msgs} msg · {conv["created"][:10]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_open:
        if is_active:
            st.markdown(
                '<span style="color:#56d364;font-size:0.8rem;padding:6px 0;'
                'display:inline-block;">Active</span>',
                unsafe_allow_html=True,
            )
        else:
            if st.button("Open", key=f"cl_open_{conv['id']}", use_container_width=True):
                switch_conv(conv["id"])
                st.rerun()

    if show_actions:
        with col_pin:
            if st.button("📌" if not is_pinned else "☐",
                         key=f"cl_pin_{conv['id']}", use_container_width=True,
                         help="Pin / unpin"):
                pin_conv(conv["id"])
                st.rerun()

        with col_del:
            if st.button("✕", key=f"cl_del_{conv['id']}", use_container_width=True,
                         help="Delete"):
                st.session_state[f"cl_confirm_{conv['id']}"] = True

    if st.session_state.get(f"cl_confirm_{conv['id']}"):
        st.warning(f"Delete **{conv['name']}**?")
        cy, cn = st.columns(2)
        if cy.button("Delete", key=f"cl_del_yes_{conv['id']}"):
            delete_conv(conv["id"])
            st.session_state.pop(f"cl_confirm_{conv['id']}", None)
            st.rerun()
        if cn.button("Keep", key=f"cl_del_no_{conv['id']}"):
            st.session_state.pop(f"cl_confirm_{conv['id']}", None)
            st.rerun()
