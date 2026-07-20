"""
ui/components/sidebar.py

Sidebar — navigation, agent status, model info, memory stats, tool list.
Phase 3: conversation history moved into chat.py sidebar section.
"""

import streamlit as st
from ui.utils.session import get_container, get_active_page, set_active_page
from config.settings import ASSISTANT_NAME, DEFAULT_MODEL


def render_sidebar() -> str:
    """Render the sidebar and return the selected page name."""
    with st.sidebar:
        # ── Logo ──────────────────────────────────────────────────────────────
        st.markdown("## 🤖 IRIS")
        st.markdown(
            '<p style="color:#8b949e;font-size:0.8rem;margin-top:-12px;">'
            "Intelligent Reasoning Information System</p>",
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Agent status ──────────────────────────────────────────────────────
        try:
            container    = get_container()
            agent_status = container.agent.status.value
            status_class = {
                "idle":    "status-idle",
                "running": "status-online",
                "paused":  "status-idle",
                "stopped": "status-offline",
            }.get(agent_status, "status-idle")
            st.markdown(
                f'**Agent:** <span class="{status_class}">⬤ {agent_status}</span>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.markdown(
                '**Agent:** <span class="status-offline">⬤ offline</span>',
                unsafe_allow_html=True,
            )

        st.markdown(f"**Model:** `{DEFAULT_MODEL}`")
        st.divider()

        # ── Navigation ────────────────────────────────────────────────────────
        pages     = ["💬 Chat", "🧠 Memory", "⚙️ Workflow", "🔧 Tools", "⚙ Settings"]
        icons_map = {
            "💬 Chat":     "Chat",
            "🧠 Memory":   "Memory",
            "⚙️ Workflow": "Workflow",
            "🔧 Tools":    "Tools",
            "⚙ Settings": "Settings",
        }

        current        = get_active_page()
        selected_label = st.radio(
            "Navigation",
            pages,
            index=next(
                (i for i, p in enumerate(pages) if icons_map[p] == current), 0
            ),
            label_visibility="collapsed",
        )
        selected_page = icons_map.get(selected_label, "Chat")
        set_active_page(selected_page)

        st.divider()

        # ── Memory stats ──────────────────────────────────────────────────────
        try:
            mm            = get_container().memory_manager
            history_count = len(mm._history)
            vector_size   = mm._vector_store.size()
            st.markdown("**Memory**")
            c1, c2 = st.columns(2)
            c1.metric("Turns",   history_count)
            c2.metric("Vectors", vector_size)
        except Exception:
            st.markdown(
                '<span style="color:#8b949e">Memory unavailable</span>',
                unsafe_allow_html=True,
            )

        # ── Tools ─────────────────────────────────────────────────────────────
        st.divider()
        try:
            tools = list(get_container().tool_manager.tools.keys())
            st.markdown("**Tools**")
            for tool in tools:
                st.markdown(
                    f'<span style="color:#56d364">⬤</span> `{tool}`',
                    unsafe_allow_html=True,
                )
        except Exception:
            st.markdown(
                '<span style="color:#8b949e">Tools unavailable</span>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown(
            '<p style="color:#8b949e;font-size:0.72rem;text-align:center;">'
            "IRIS v1.0 — Local AI Agent</p>",
            unsafe_allow_html=True,
        )

    return selected_page
