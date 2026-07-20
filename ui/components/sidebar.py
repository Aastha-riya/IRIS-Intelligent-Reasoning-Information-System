"""
ui/components/sidebar.py

Sidebar — v1.0 production navigation.
Pages: Dashboard · Chat · Memory · Conversations · Workflow · Tools · Logs · Settings
"""

import streamlit as st
from ui.utils.session import get_container, get_active_page, set_active_page
from ui.utils.prefs   import get_pref
import config.settings as cfg


def render_sidebar() -> str:
    """Render the sidebar and return the selected page name."""
    with st.sidebar:
        # ── Logo ──────────────────────────────────────────────────────────────
        st.markdown(
            '<div style="text-align:center;padding:12px 0 4px;">'
            '<div style="font-size:2rem;">🤖</div>'
            '<div style="font-weight:700;font-size:1.1rem;">IRIS</div>'
            '<div style="color:#8b949e;font-size:0.72rem;margin-top:-2px;">'
            'v1.0 · Local AI Agent</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Agent + model status ──────────────────────────────────────────────
        try:
            container    = get_container()
            agent_status = container.agent.status.value
            color = {"idle": "#56d364", "running": "#e3b341",
                     "paused": "#8b949e", "stopped": "#f85149"}.get(agent_status, "#8b949e")
            st.markdown(
                f'<div style="font-size:0.82rem;">'
                f'<span style="color:#8b949e;">Agent</span> '
                f'<span style="color:{color};font-weight:600;">⬤ {agent_status}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.markdown(
                '<div style="font-size:0.82rem;color:#f85149;">⬤ offline</div>',
                unsafe_allow_html=True,
            )

        model = get_pref("model") or cfg.DEFAULT_MODEL
        st.markdown(
            f'<div style="font-size:0.78rem;color:#8b949e;margin-top:2px;">'
            f'Model: <code>{model}</code></div>',
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Navigation ────────────────────────────────────────────────────────
        pages = [
            "🏠 Dashboard",
            "💬 Chat",
            "🧠 Memory",
            "💬 Conversations",
            "⚙️ Workflow",
            "🔧 Tools",
            "📋 Logs",
            "⚙ Settings",
        ]
        icons_map = {
            "🏠 Dashboard":     "Dashboard",
            "💬 Chat":          "Chat",
            "🧠 Memory":        "Memory",
            "💬 Conversations": "Conversations",
            "⚙️ Workflow":      "Workflow",
            "🔧 Tools":         "Tools",
            "📋 Logs":          "Logs",
            "⚙ Settings":      "Settings",
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
        selected_page = icons_map.get(selected_label, "Dashboard")
        set_active_page(selected_page)

        st.divider()

        # ── Memory stats ──────────────────────────────────────────────────────
        try:
            mm = get_container().memory_manager
            st.markdown(
                f'<div style="font-size:0.78rem;color:#8b949e;">'
                f'💾 {len(mm._history)} turns · {mm._vector_store.size()} vectors'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

        # ── Enabled tools ─────────────────────────────────────────────────────
        try:
            from ui.utils.prefs import is_tool_enabled
            tools = list(get_container().tool_manager.tools.keys())
            enabled = [t for t in tools if is_tool_enabled(t)]
            st.markdown(
                f'<div style="font-size:0.78rem;color:#8b949e;margin-top:4px;">'
                f'🔧 {len(enabled)}/{len(tools)} tools active'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

        st.divider()

        # ── Quick new chat ────────────────────────────────────────────────────
        if st.button("＋ New Chat", key="sb_new_chat", use_container_width=True):
            from ui.utils.session import new_conv
            new_conv()
            set_active_page("Chat")
            st.rerun()

    return selected_page
