"""
ui/pages/memory.py

Memory Manager page — Phase 4 full implementation.

Sections:
    Dashboard   — stats, quick actions
    History     — browse/search/delete individual turns
    Semantic    — vector store search with similarity scores
    Import      — paste raw text to store as a memory
"""

from __future__ import annotations

import streamlit as st

from ui.utils.session import get_container


def render() -> None:
    st.markdown("## 🧠 Memory Manager")
    st.markdown(
        '<p style="color:#8b949e;">Browse, search, and manage IRIS long-term memory.</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    try:
        container = get_container()
        mm        = container.memory_manager
    except Exception as exc:
        st.error(f"Memory unavailable: {exc}")
        return

    tab_dash, tab_history, tab_semantic, tab_store = st.tabs([
        "📊 Dashboard",
        "📜 Conversation History",
        "🔍 Semantic Search",
        "➕ Store Memory",
    ])

    with tab_dash:
        _section_dashboard(mm)

    with tab_history:
        _section_history(mm)

    with tab_semantic:
        _section_semantic(mm)

    with tab_store:
        _section_store(mm)


# ── Dashboard ─────────────────────────────────────────────────────────────────

def _section_dashboard(mm) -> None:
    st.subheader("📊 Memory Dashboard")

    # ── Metrics ───────────────────────────────────────────────────────────────
    try:
        turns   = len(mm._history)
        vectors = mm._vector_store.size()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Conversation Turns",  turns)
        c2.metric("Vector Memories",     vectors)
        c3.metric("Context Window",      "10 turns")
        c4.metric("RAG Memories / Call", "5")
    except Exception:
        st.caption("Stats unavailable.")

    st.divider()

    # ── Quick actions ─────────────────────────────────────────────────────────
    st.markdown("**Quick actions**")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Reload from disk", key="mem_reload", use_container_width=True):
            try:
                raw = mm._history_storage.read()
                from memory.history import ConversationHistory
                mm._history = ConversationHistory(raw)
                st.success(f"Reloaded {len(mm._history)} turns.")
            except Exception as e:
                st.error(str(e))

    with col2:
        if st.button("🗑️ Clear all memory", key="mem_clear_dash", use_container_width=True):
            st.session_state["_mem_confirm_clear"] = True

    with col3:
        if st.button("📋 Copy stats", key="mem_copy_stats", use_container_width=True):
            try:
                stats = (
                    f"Turns: {len(mm._history)} | "
                    f"Vectors: {mm._vector_store.size()}"
                )
                st.session_state["_clipboard"] = stats
                st.toast("Stats copied!", icon="✅")
            except Exception:
                pass

    if st.session_state.get("_mem_confirm_clear"):
        st.warning("⚠️ This will erase all conversation history and vector memories permanently.")
        cy, cn = st.columns(2)
        if cy.button("Yes, clear everything", key="mem_confirm_yes"):
            mm.clear_memory()
            st.success("All memory cleared.")
            st.session_state.pop("_mem_confirm_clear", None)
            st.rerun()
        if cn.button("Cancel", key="mem_confirm_no"):
            st.session_state.pop("_mem_confirm_clear", None)
            st.rerun()


# ── Conversation history ──────────────────────────────────────────────────────

def _section_history(mm) -> None:
    st.subheader("📜 Conversation History")

    try:
        turns = mm._history.all_turns()
    except Exception as exc:
        st.error(f"Could not load history: {exc}")
        return

    if not turns:
        st.markdown('<p style="color:#8b949e;">No conversation history yet.</p>',
                    unsafe_allow_html=True)
        return

    # ── Search filter ─────────────────────────────────────────────────────────
    search_q = st.text_input(
        "Filter turns",
        placeholder="Search within history...",
        key="hist_filter",
    )

    filtered = [
        t for t in turns
        if not search_q
        or search_q.lower() in t.get("user", "").lower()
        or search_q.lower() in t.get("assistant", "").lower()
    ]

    st.caption(f"Showing {len(filtered)} of {len(turns)} turns.")
    st.divider()

    # ── Turn list ─────────────────────────────────────────────────────────────
    for i, turn in enumerate(reversed(filtered)):
        real_idx = len(turns) - 1 - i
        ts       = turn.get("time", "")
        preview  = turn.get("user", "")[:60]

        with st.expander(f"Turn {real_idx + 1} — {ts}  ·  \"{preview}...\"",
                         expanded=False):
            col_content, col_actions = st.columns([8, 2])

            with col_content:
                st.markdown(f"**You:** {turn.get('user', '')}")
                st.markdown(f"**IRIS:** {turn.get('assistant', '')}")

            with col_actions:
                # Delete this turn
                if st.button("🗑", key=f"del_turn_{real_idx}",
                             help="Delete this turn"):
                    st.session_state[f"_del_turn_{real_idx}"] = True

            if st.session_state.get(f"_del_turn_{real_idx}"):
                cy, cn = st.columns(2)
                if cy.button("Delete", key=f"del_turn_yes_{real_idx}"):
                    try:
                        all_turns = mm._history.all_turns()
                        all_turns.pop(real_idx)
                        # Rebuild history and re-persist
                        mm._history._turns = all_turns
                        mm._history_storage.write(all_turns)
                        st.success("Turn deleted.")
                        st.session_state.pop(f"_del_turn_{real_idx}", None)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                if cn.button("Keep", key=f"del_turn_no_{real_idx}"):
                    st.session_state.pop(f"_del_turn_{real_idx}", None)
                    st.rerun()


# ── Semantic search ───────────────────────────────────────────────────────────

def _section_semantic(mm) -> None:
    st.subheader("🔍 Semantic Search")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "Search memories by meaning, not keyword. "
        "Results are ranked by similarity + importance + recency.</p>",
        unsafe_allow_html=True,
    )

    query = st.text_input(
        "Search query",
        placeholder="e.g. What programming languages do I prefer?",
        key="sem_search_q",
    )

    top_k = st.slider("Max results", min_value=1, max_value=20, value=5, key="sem_topk")

    if st.button("🔍 Search", key="sem_search_btn") and query.strip():
        with st.spinner("Searching semantic memory..."):
            try:
                results = mm.retrieve_memory(query.strip())
            except Exception as exc:
                st.error(f"Search failed: {exc}")
                return

        if not results:
            st.info("No relevant memories found for that query.")
            return

        st.caption(f"Found {len(results)} result(s).")
        for i, mem in enumerate(results[:top_k], 1):
            text       = mem.text if hasattr(mem, "text") else str(mem)
            score      = mem.rank_score if hasattr(mem, "rank_score") else 0
            similarity = mem.similarity_score if hasattr(mem, "similarity_score") else 0
            ts         = mem.timestamp if hasattr(mem, "timestamp") else ""

            st.markdown(
                f'<div style="background:#21262d;border:1px solid #30363d;'
                f'border-radius:8px;padding:10px 14px;margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'margin-bottom:6px;">'
                f'<strong>#{i}</strong>'
                f'<span style="color:#8b949e;font-size:0.78rem;">'
                f'score={score:.3f} · sim={similarity:.3f}'
                f'{" · " + ts if ts and ts != "unknown" else ""}</span></div>'
                f'<span style="color:#e0e0e0;font-size:0.88rem;">{text}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── Store memory ──────────────────────────────────────────────────────────────

def _section_store(mm) -> None:
    st.subheader("➕ Store a Memory")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "Add any text as a permanent semantic memory. "
        "IRIS will be able to recall it in future conversations.</p>",
        unsafe_allow_html=True,
    )

    text = st.text_area(
        "Memory text",
        placeholder="e.g. The user prefers Python over Java. Their favourite IDE is VS Code.",
        height=120,
        key="store_mem_text",
    )

    importance = st.slider(
        "Importance",
        min_value=0.0, max_value=1.0,
        value=0.8, step=0.05,
        help="Higher importance → more likely to be retrieved in future searches.",
        key="store_mem_importance",
    )

    if st.button("💾 Store memory", key="store_mem_btn"):
        if not text.strip():
            st.warning("Please enter some text to store.")
            return
        try:
            mm.store_memory(text.strip())
            st.success("Memory stored successfully.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not store memory: {exc}")
