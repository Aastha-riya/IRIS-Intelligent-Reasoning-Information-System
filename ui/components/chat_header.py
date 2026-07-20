"""
ui/components/chat_header.py

Improvement 1 — Better Header.

Shows:
    🤖 IRIS Assistant   Model: llama3.2   Status: Ready ⬤
    [Conversation name]  [＋] [🗑] [✏] [✕]
"""

from __future__ import annotations

import streamlit as st

from ui.utils.prefs   import get_pref
from ui.utils.session import (
    get_agent_status,
    get_active_conv,
    get_thinking_stage,
    new_conv,
    clear_chat,
    rename_conv,
    delete_conv,
    _active_conv_id,
)

_STATUS_COLOR = {
    "idle":    ("#56d364", "Ready"),
    "running": ("#e3b341", "Working"),
    "paused":  ("#8b949e", "Paused"),
    "stopped": ("#f85149", "Stopped"),
    "offline": ("#f85149", "Offline"),
}


def render_chat_header() -> None:
    """Render the improved chat header with model + status info."""
    conv         = get_active_conv()
    agent_status = get_agent_status()
    stage        = get_thinking_stage()
    model        = get_pref("model") or "llama3.2"
    color, label = _STATUS_COLOR.get(agent_status, ("#8b949e", agent_status))
    status_text  = stage if stage and agent_status == "running" else label

    # ── Top banner: IRIS branding + live model + status ───────────────────────
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'background:#161b22;border:1px solid #30363d;border-radius:12px;'
        f'padding:12px 18px;margin-bottom:10px;">'

        # Left: logo + name
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<span style="font-size:1.5rem;">🤖</span>'
        f'<div>'
        f'<div style="font-weight:700;font-size:1rem;">IRIS Assistant</div>'
        f'<div style="color:#8b949e;font-size:0.75rem;">{conv["name"][:40]}</div>'
        f'</div>'
        f'</div>'

        # Right: model chip + status badge
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'<div style="background:#21262d;border:1px solid #30363d;border-radius:8px;'
        f'padding:4px 10px;font-size:0.78rem;color:#8b949e;">'
        f'⚙ Model: <code style="color:#79c0ff;">{model}</code>'
        f'</div>'
        f'<div style="background:{color}22;border:1px solid {color};border-radius:8px;'
        f'padding:4px 10px;font-size:0.78rem;font-weight:600;color:{color};">'
        f'⬤ {status_text}'
        f'</div>'
        f'</div>'

        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Action row ────────────────────────────────────────────────────────────
    col_spacer, col_new, col_clear, col_rename, col_delete = st.columns([8, 1, 1, 1, 1])

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
        if st.button("✏", key="hdr_rename", help="Rename",
                     use_container_width=True):
            st.session_state["renaming"] = True
    with col_delete:
        if st.button("✕", key="hdr_delete", help="Delete",
                     use_container_width=True):
            st.session_state["confirm_delete"] = True

    # ── Rename form ───────────────────────────────────────────────────────────
    if st.session_state.get("renaming"):
        with st.form("rename_form", clear_on_submit=True):
            new_name  = st.text_input("New name", value=conv["name"])
            ok, cancel = st.columns(2)
            saved     = ok.form_submit_button("Save")
            cancelled = cancel.form_submit_button("Cancel")
        if saved and new_name.strip():
            rename_conv(_active_conv_id(), new_name)
            st.session_state.pop("renaming", None)
            st.rerun()
        if cancelled:
            st.session_state.pop("renaming", None)
            st.rerun()

    # ── Delete confirmation ───────────────────────────────────────────────────
    if st.session_state.get("confirm_delete"):
        st.warning(f"Delete **{conv['name']}**?", icon="⚠️")
        cy, cn = st.columns(2)
        if cy.button("Yes, delete", key="del_yes"):
            delete_conv(_active_conv_id())
            st.session_state.pop("confirm_delete", None)
            st.rerun()
        if cn.button("Cancel", key="del_no"):
            st.session_state.pop("confirm_delete", None)
            st.rerun()

    st.divider()
