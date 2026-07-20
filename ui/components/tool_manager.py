"""
ui/components/tool_manager.py

Reusable tool manager widget — used by both tools.py page and settings.py.
Renders tool cards with enable/disable and status.
"""

from __future__ import annotations

import streamlit as st

from ui.utils.prefs import is_tool_enabled, toggle_tool


_TOOL_META = {
    "calculator":      {"icon": "🧮", "desc": "Evaluates math expressions."},
    "file_reader":     {"icon": "📄", "desc": "Reads local file contents."},
    "project_scanner": {"icon": "📁", "desc": "Scans project directories."},
    "internet":        {"icon": "🌐", "desc": "DuckDuckGo web search."},
}


def render_tool_cards(tools: dict, compact: bool = False) -> None:
    """
    Render tool cards with enable/disable toggles.

    Args:
        tools:   Dict from ToolManager.tools.
        compact: If True, renders a more condensed list.
    """
    for name in tools:
        meta    = _TOOL_META.get(name, {"icon": "🔧", "desc": ""})
        enabled = is_tool_enabled(name)
        color   = "#56d364" if enabled else "#8b949e"
        label   = "Enabled" if enabled else "Disabled"

        if compact:
            col_icon, col_name, col_btn = st.columns([1, 7, 2])
            col_icon.markdown(meta["icon"])
            col_name.markdown(
                f'`{name}` <span style="color:{color};font-size:0.75rem;">⬤ {label}</span>',
                unsafe_allow_html=True,
            )
            if col_btn.button(
                "Disable" if enabled else "Enable",
                key=f"tm_toggle_{name}",
                use_container_width=True,
            ):
                toggle_tool(name)
                st.rerun()
        else:
            col_icon, col_body, col_btn = st.columns([1, 8, 2])
            col_icon.markdown(
                f'<div style="font-size:1.5rem;padding-top:6px;">{meta["icon"]}</div>',
                unsafe_allow_html=True,
            )
            col_body.markdown(
                f'**`{name}`** <span style="color:{color};font-size:0.78rem;">⬤ {label}</span>'
                f'<br><span style="color:#8b949e;font-size:0.82rem;">{meta["desc"]}</span>',
                unsafe_allow_html=True,
            )
            if col_btn.button(
                "Disable" if enabled else "Enable",
                key=f"tm_toggle_{name}",
                type="secondary" if enabled else "primary",
                use_container_width=True,
            ):
                toggle_tool(name)
                st.rerun()
            st.markdown("---")
