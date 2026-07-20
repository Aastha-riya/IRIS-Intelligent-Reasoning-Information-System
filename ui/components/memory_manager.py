"""
ui/components/memory_manager.py

Memory manager component — reusable widget for memory operations.
Used by both memory.py page and settings.py Advanced tab.
"""

from __future__ import annotations

import streamlit as st


def render_memory_stats(mm) -> None:
    """Render a 4-metric memory stats row."""
    try:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Conversation Turns",  len(mm._history))
        c2.metric("Vector Memories",     mm._vector_store.size())
        c3.metric("Context Window",      "10 turns")
        c4.metric("RAG / Prompt",        "5 memories")
    except Exception:
        st.caption("Memory stats unavailable.")


def render_memory_actions(mm) -> None:
    """Render quick-action buttons for memory management."""
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Reload", key="mm_reload", use_container_width=True,
                     help="Reload history from disk"):
            try:
                raw = mm._history_storage.read()
                from memory.history import ConversationHistory
                mm._history = ConversationHistory(raw)
                st.success(f"Reloaded {len(mm._history)} turns.")
            except Exception as e:
                st.error(str(e))

    with col2:
        if st.button("🗑️ Clear", key="mm_clear", use_container_width=True,
                     help="Erase all memory permanently"):
            st.session_state["mm_confirm_clear"] = True

    with col3:
        if st.button("📋 Stats", key="mm_stats_copy", use_container_width=True):
            try:
                st.toast(
                    f"Turns: {len(mm._history)} | Vectors: {mm._vector_store.size()}",
                    icon="📊",
                )
            except Exception:
                pass

    if st.session_state.get("mm_confirm_clear"):
        st.warning("⚠️ This will erase all conversation history and vector memories.")
        cy, cn = st.columns(2)
        if cy.button("Yes, clear", key="mm_clear_yes"):
            mm.clear_memory()
            st.success("Memory cleared.")
            st.session_state.pop("mm_confirm_clear", None)
            st.rerun()
        if cn.button("Cancel", key="mm_clear_no"):
            st.session_state.pop("mm_confirm_clear", None)
            st.rerun()
