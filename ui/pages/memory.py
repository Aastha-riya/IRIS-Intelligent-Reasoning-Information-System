"""
ui/pages/memory.py

Memory page — view conversation history, vector store stats, and search memory.
"""

import streamlit as st

from ui.components.header import render_header
from ui.components.status import error as show_error
from ui.utils.session     import get_container


def render() -> None:
    render_header("Memory", "Conversation history and semantic store")

    try:
        container = get_container()
        mm        = container.memory_manager
    except Exception as exc:
        show_error(f"Could not load memory: {exc}")
        return

    # ── Stats row ─────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    try:
        history_count = len(mm._history)
        vector_size   = mm._vector_store.size()
        col1.metric("Conversation Turns", history_count)
        col2.metric("Vector Memories",    vector_size)
        col3.metric("Context Window",     f"{history_count} / {15}")
    except Exception:
        col1.metric("Turns",   "—")
        col2.metric("Vectors", "—")
        col3.metric("Window",  "—")

    st.divider()

    # ── Conversation history ──────────────────────────────────────────────────
    st.subheader("📜 Conversation History")

    try:
        turns = mm._history.all_turns()
        if not turns:
            st.markdown(
                '<p style="color:#8b949e;">No conversation history yet.</p>',
                unsafe_allow_html=True,
            )
        else:
            for i, turn in enumerate(reversed(turns), 1):
                with st.expander(
                    f"Turn {len(turns) - i + 1} — {turn.get('time', '')}",
                    expanded=(i == 1),
                ):
                    st.markdown(f"**You:** {turn.get('user', '')}")
                    st.markdown(f"**IRIS:** {turn.get('assistant', '')}")
    except Exception as exc:
        show_error(f"Could not load history: {exc}")

    st.divider()

    # ── Semantic search ────────────────────────────────────────────────────────
    st.subheader("🔍 Search Memory")
    query = st.text_input("Search query", placeholder="What do you remember about...?",
                          key="memory_search")
    if st.button("Search", key="mem_search_btn") and query.strip():
        with st.spinner("Searching..."):
            try:
                results = mm.retrieve_memory(query.strip())
                if not results:
                    st.markdown(
                        '<p style="color:#8b949e;">No relevant memories found.</p>',
                        unsafe_allow_html=True,
                    )
                else:
                    for i, mem in enumerate(results, 1):
                        text = mem.text if hasattr(mem, "text") else str(mem)
                        score = mem.rank_score if hasattr(mem, "rank_score") else 0
                        st.markdown(
                            f'<div class="iris-bubble">'
                            f'<strong>#{i}</strong> '
                            f'<span style="color:#8b949e;font-size:0.8rem;">'
                            f'score={score:.3f}</span><br>{text}</div>',
                            unsafe_allow_html=True,
                        )
            except Exception as exc:
                show_error(f"Search failed: {exc}")

    st.divider()

    # ── Danger zone ───────────────────────────────────────────────────────────
    st.subheader("⚠️ Danger Zone")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "Clearing memory is permanent and cannot be undone.</p>",
        unsafe_allow_html=True,
    )
    if st.button("🗑️ Clear All Memory", key="clear_memory_btn"):
        confirm = st.checkbox("Yes, I understand this is permanent", key="confirm_clear")
        if confirm:
            try:
                mm.clear_memory()
                st.success("Memory cleared successfully.")
                st.rerun()
            except Exception as exc:
                show_error(f"Could not clear memory: {exc}")
