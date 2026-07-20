"""
ui/components/tool_status.py

Tool activity display — shows which tool is running and its result.

Examples:
    🔧 Calculator — Running...
    ✅ Calculator — 3796

    🔧 File Reader — Reading README.md...
    ✅ File Reader — 2 KB read

Usage:
    indicator = ToolStatusIndicator()
    indicator.start("calculator", "52 * 73")
    result = tool.execute(query)
    indicator.done("calculator", str(result))
"""

from __future__ import annotations

import streamlit as st


# ── Tool icons ────────────────────────────────────────────────────────────────

_TOOL_ICON = {
    "calculator":      "🧮",
    "file_reader":     "📄",
    "project_scanner": "📁",
    "internet":        "🌐",
    "llm":             "🧠",
    "none":            "⚙️",
}


# ── Public API ────────────────────────────────────────────────────────────────

class ToolStatusIndicator:
    """
    Shows real-time tool activity.
    Call start() when a tool begins, done() when it finishes.
    """

    def __init__(self) -> None:
        self._slot = st.empty()

    def start(self, tool_name: str, query: str = "") -> None:
        """Show a 'running' indicator for the given tool."""
        icon  = _TOOL_ICON.get(tool_name.lower(), "🔧")
        label = query[:60] + ("..." if len(query) > 60 else "") if query else ""
        self._slot.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'background:#21262d;border:1px solid #30363d;border-radius:8px;'
            f'padding:8px 14px;margin:4px 0;">'
            f'{icon} <strong>{tool_name}</strong>'
            f'<span style="color:#8b949e;font-size:0.85rem;"> — Running...</span>'
            f'{"<br><code style=color:#8b949e;font-size:0.78rem>" + label + "</code>" if label else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

    def done(self, tool_name: str, result_preview: str = "") -> None:
        """Replace the running indicator with a completion badge."""
        icon    = _TOOL_ICON.get(tool_name.lower(), "🔧")
        preview = result_preview[:80] + ("..." if len(result_preview) > 80 else "")
        self._slot.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'background:#2ea04311;border:1px solid #2ea043;border-radius:8px;'
            f'padding:6px 14px;margin:4px 0;font-size:0.85rem;">'
            f'✅ {icon} <strong>{tool_name}</strong>'
            f'{"<span style=color:#8b949e;> — " + preview + "</span>" if preview else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

    def error(self, tool_name: str, error_msg: str = "") -> None:
        """Show an error badge for the tool."""
        icon = _TOOL_ICON.get(tool_name.lower(), "🔧")
        self._slot.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'background:#f8514922;border:1px solid #f85149;border-radius:8px;'
            f'padding:6px 14px;margin:4px 0;font-size:0.85rem;">'
            f'❌ {icon} <strong>{tool_name}</strong>'
            f'{"<span style=color:#f85149;> — " + error_msg[:60] + "</span>" if error_msg else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

    def clear(self) -> None:
        """Remove the indicator."""
        self._slot.empty()


def render_agent_status_panel(
    stage:     str = "",
    tool_name: str = "",
    is_done:   bool = False,
) -> None:
    """
    Render a compact status panel showing current agent stage.

    Args:
        stage:     Current stage label (e.g. "Planning", "Executing").
        tool_name: Active tool name (empty if not using a tool).
        is_done:   True to show completion state.
    """
    if is_done:
        st.markdown(
            '<div style="background:#2ea04311;border:1px solid #2ea043;'
            'border-radius:8px;padding:8px 14px;font-size:0.85rem;color:#56d364;">'
            '✅ Response ready</div>',
            unsafe_allow_html=True,
        )
        return

    icon  = _TOOL_ICON.get(tool_name.lower(), "⚙️") if tool_name else "🧠"
    label = f"{stage}" if stage else "Thinking..."
    extra = f" · {tool_name}" if tool_name else ""

    st.markdown(
        f'<div style="background:#21262d;border:1px solid #30363d;'
        f'border-radius:8px;padding:8px 14px;font-size:0.85rem;color:#8b949e;">'
        f'{icon} {label}{extra}</div>',
        unsafe_allow_html=True,
    )
