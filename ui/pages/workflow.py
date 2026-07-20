"""
ui/pages/workflow.py

Two-tab page — Phase 4 full implementation.

Tab 1: Conversation Manager
    New / Rename / Delete / Pin / Search / Export / Import conversations.

Tab 2: Workflow Runner
    Manually trigger a multi-step workflow and inspect the task timeline.
"""

from __future__ import annotations

import json

import streamlit as st

from ui.components.export_chat   import render_export_buttons
from ui.components.workflow_panel import render_workflow_panel
from ui.utils.session import (
    get_container,
    new_conv,
    rename_conv,
    delete_conv,
    switch_conv,
    pin_conv,
    search_conversations,
    list_conversations,
    _active_conv_id,
    get_messages,
)


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("## ⚙️ Workflow & Conversations")
    st.divider()

    tab_convs, tab_workflow = st.tabs([
        "💬 Conversation Manager",
        "📋 Workflow Runner",
    ])

    with tab_convs:
        _section_conversations()

    with tab_workflow:
        _section_workflow_runner()


# ── Conversation Manager ──────────────────────────────────────────────────────

def _section_conversations() -> None:
    st.subheader("💬 Conversation Manager")

    # ── Top action bar ────────────────────────────────────────────────────────
    col_new, col_search, col_spacer = st.columns([2, 5, 3])

    with col_new:
        if st.button("＋ New conversation", key="cm_new", type="primary",
                     use_container_width=True):
            new_conv()
            st.rerun()

    with col_search:
        search_q = st.text_input(
            "Search",
            placeholder="Search conversations...",
            key="cm_search",
            label_visibility="collapsed",
        )

    st.divider()

    # ── Import ────────────────────────────────────────────────────────────────
    with st.expander("⬆️ Import conversation"):
        uploaded = st.file_uploader(
            "Upload a conversation JSON file",
            type=["json"],
            key="cm_import_file",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            try:
                data = json.loads(uploaded.read().decode("utf-8"))
                _import_conversation(data)
                st.success("Conversation imported.")
                st.rerun()
            except Exception as exc:
                st.error(f"Import failed: {exc}")

    st.divider()

    # ── Conversation list ─────────────────────────────────────────────────────
    convs      = search_conversations(search_q) if search_q else list_conversations()
    active_id  = _active_conv_id()

    if not convs:
        st.markdown(
            '<p style="color:#8b949e;">No conversations found.</p>',
            unsafe_allow_html=True,
        )
        return

    st.caption(f"{len(convs)} conversation(s)")

    for conv in convs:
        _render_conv_row(conv, active_id)


def _render_conv_row(conv: dict, active_id: str) -> None:
    """Render one conversation row with actions."""
    is_active = conv["id"] == active_id
    is_pinned = conv.get("pinned", False)
    msg_count = len(conv["messages"])

    border_color = "#1f6feb" if is_active else "#30363d"
    pin_label    = "📌" if is_pinned else "☐"

    with st.container():
        col_pin, col_info, col_open, col_rename, col_export, col_delete = st.columns(
            [1, 6, 2, 2, 2, 1]
        )

        # Pin button
        with col_pin:
            if st.button(pin_label, key=f"pin_{conv['id']}",
                         help="Pin / unpin", use_container_width=True):
                pin_conv(conv["id"])
                st.rerun()

        # Info
        with col_info:
            active_dot = "▶ " if is_active else ""
            st.markdown(
                f'<div style="padding:4px 0;border-left:3px solid {border_color};'
                f'padding-left:10px;">'
                f'<strong>{active_dot}{conv["name"]}</strong>'
                f'<span style="color:#8b949e;font-size:0.78rem;">'
                f' · {msg_count} message(s) · {conv["created"][:10]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Open
        with col_open:
            if not is_active:
                if st.button("Open", key=f"open_{conv['id']}", use_container_width=True):
                    switch_conv(conv["id"])
                    st.rerun()
            else:
                st.markdown(
                    '<span style="color:#56d364;font-size:0.85rem;">Active</span>',
                    unsafe_allow_html=True,
                )

        # Rename
        with col_rename:
            if st.button("✏", key=f"rename_{conv['id']}",
                         help="Rename", use_container_width=True):
                st.session_state[f"_renaming_{conv['id']}"] = True

        # Export
        with col_export:
            export_data = json.dumps(_conv_to_export(conv), indent=2, ensure_ascii=False)
            st.download_button(
                label     = "⬇",
                data      = export_data.encode("utf-8"),
                file_name = f"{conv['name'].replace(' ', '_')}.json",
                mime      = "application/json",
                key       = f"export_{conv['id']}",
                help      = "Export as JSON",
                use_container_width = True,
            )

        # Delete
        with col_delete:
            if st.button("✕", key=f"del_{conv['id']}",
                         help="Delete", use_container_width=True):
                st.session_state[f"_del_conv_{conv['id']}"] = True

    # ── Inline rename form ────────────────────────────────────────────────────
    if st.session_state.get(f"_renaming_{conv['id']}"):
        with st.form(key=f"rename_form_{conv['id']}", clear_on_submit=True):
            new_name = st.text_input("New name", value=conv["name"])
            ok, cancel = st.columns(2)
            saved     = ok.form_submit_button("Save")
            cancelled = cancel.form_submit_button("Cancel")
        if saved and new_name.strip():
            rename_conv(conv["id"], new_name.strip())
            st.session_state.pop(f"_renaming_{conv['id']}", None)
            st.rerun()
        if cancelled:
            st.session_state.pop(f"_renaming_{conv['id']}", None)
            st.rerun()

    # ── Delete confirmation ───────────────────────────────────────────────────
    if st.session_state.get(f"_del_conv_{conv['id']}"):
        st.warning(f"Delete **{conv['name']}**? This cannot be undone.")
        cy, cn = st.columns(2)
        if cy.button("Delete", key=f"del_yes_{conv['id']}"):
            delete_conv(conv["id"])
            st.session_state.pop(f"_del_conv_{conv['id']}", None)
            st.rerun()
        if cn.button("Keep", key=f"del_no_{conv['id']}"):
            st.session_state.pop(f"_del_conv_{conv['id']}", None)
            st.rerun()

    # ── Export preview (Markdown) ─────────────────────────────────────────────
    with st.expander(f"📄 Export options — {conv['name']}", expanded=False):
        render_export_buttons(conv["messages"], conv["name"])


# ── Workflow Runner ───────────────────────────────────────────────────────────

def _section_workflow_runner() -> None:
    st.subheader("📋 Workflow Runner")
    st.markdown(
        '<p style="color:#8b949e;">'
        "Run a multi-step goal through the full IRIS pipeline: "
        "Planner → Executor → Reflection.</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    try:
        container = get_container()
        workflow  = container.workflow
    except Exception as exc:
        st.error(f"Workflow engine unavailable: {exc}")
        return

    goal = st.text_area(
        "Goal",
        placeholder="e.g. Analyse the project structure and generate a summary",
        height=100,
        key="wf_goal_input",
    )

    col_run, col_clear = st.columns([2, 8])
    run_clicked = col_run.button("▶ Run workflow", key="wf_run", type="primary")

    if run_clicked:
        if not goal.strip():
            st.warning("Please enter a goal.")
            return

        with st.spinner("🔄 Running workflow..."):
            try:
                result = workflow.run(goal.strip())
            except Exception as exc:
                st.error(f"Workflow error: {exc}")
                return

        # ── Result ────────────────────────────────────────────────────────────
        st.divider()

        if result.succeeded():
            st.success(
                f"✅ Completed in {result.total_time:.2f}s — "
                f"{result.cycles} cycle(s)"
            )
        else:
            st.error(f"❌ Failed: {result.error or 'Unknown error'}")

        # ── Task timeline ─────────────────────────────────────────────────────
        if result.plan:
            render_workflow_panel(result)

        # ── Reflection ────────────────────────────────────────────────────────
        if result.reflection_summary:
            with st.expander("🔍 Reflection summary"):
                st.markdown(result.reflection_summary)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _conv_to_export(conv: dict) -> dict:
    """Return a clean export-safe dict for a conversation."""
    return {
        "id":       conv["id"],
        "name":     conv["name"],
        "created":  conv["created"],
        "messages": [
            {
                "role":      m["role"],
                "content":   m["content"],
                "decision":  m.get("decision", ""),
                "timestamp": m.get("timestamp", ""),
            }
            for m in conv["messages"]
        ],
    }


def _import_conversation(data: dict) -> None:
    """Import a conversation from a previously exported JSON dict."""
    import uuid as _uuid
    from ui.utils.session import _all_conversations, _now

    conv_id = str(_uuid.uuid4())   # always give a fresh ID on import
    convs   = _all_conversations()
    convs[conv_id] = {
        "id":       conv_id,
        "name":     data.get("name", "Imported Chat"),
        "messages": data.get("messages", []),
        "created":  data.get("created", _now()),
        "pinned":   False,
    }
    st.session_state["active_conv_id"] = conv_id
