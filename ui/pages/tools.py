"""
ui/pages/tools.py

Tool Manager page — Phase 4 full implementation.

Features:
    - View all registered tools with descriptions
    - Enable / disable individual tools per session
    - Tool health check (test execute with a safe payload)
    - Direct test interface
    - Tool status badges
"""

from __future__ import annotations

import streamlit as st

from ui.utils.session import get_container
from ui.utils.prefs   import is_tool_enabled, toggle_tool


# ── Tool metadata ─────────────────────────────────────────────────────────────

_TOOL_META: dict[str, dict] = {
    "calculator": {
        "icon":        "🧮",
        "description": "Evaluates mathematical expressions from natural language.",
        "example":     "calculate 52 * 73",
        "health_q":    "calculate 1 + 1",
        "expected":    "2",
    },
    "file_reader": {
        "icon":        "📄",
        "description": "Reads and returns the content of a local file.",
        "example":     "read README.md",
        "health_q":    "read README.md",
        "expected":    None,   # any non-empty response is fine
    },
    "project_scanner": {
        "icon":        "📁",
        "description": "Scans a project directory and lists source files by extension.",
        "example":     "scan .",
        "health_q":    "scan .",
        "expected":    None,
    },
    "internet": {
        "icon":        "🌐",
        "description": "Searches the web using DuckDuckGo and returns top results.",
        "example":     "search Python async tutorial",
        "health_q":    "search Python",
        "expected":    None,
    },
}

_DEFAULT_META = {
    "icon": "🔧",
    "description": "Custom tool.",
    "example": "",
    "health_q": "",
    "expected": None,
}


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("## 🔧 Tool Manager")
    st.markdown(
        '<p style="color:#8b949e;">Manage, test, and monitor IRIS tools.</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    try:
        container    = get_container()
        tool_manager = container.tool_manager
        tools        = tool_manager.tools
    except Exception as exc:
        st.error(f"ToolManager unavailable: {exc}")
        return

    tab_all, tab_test, tab_health = st.tabs([
        f"📦 All Tools ({len(tools)})",
        "🧪 Test Tool",
        "❤️ Health Check",
    ])

    with tab_all:
        _section_all_tools(tools)

    with tab_test:
        _section_test(tools)

    with tab_health:
        _section_health(tools)


# ── All tools ─────────────────────────────────────────────────────────────────

def _section_all_tools(tools: dict) -> None:
    st.subheader(f"📦 Registered Tools")

    for name, tool in tools.items():
        meta    = _TOOL_META.get(name, _DEFAULT_META)
        enabled = is_tool_enabled(name)
        status_color = "#56d364" if enabled else "#8b949e"
        status_label = "Enabled" if enabled else "Disabled"

        with st.container():
            col_icon, col_body, col_toggle = st.columns([1, 8, 2])

            with col_icon:
                st.markdown(
                    f'<div style="font-size:1.6rem;padding-top:6px;">{meta["icon"]}</div>',
                    unsafe_allow_html=True,
                )

            with col_body:
                st.markdown(
                    f'<div style="padding:6px 0;">'
                    f'<strong style="font-size:1rem;">`{name}`</strong>'
                    f'<span style="color:{status_color};font-size:0.78rem;'
                    f'margin-left:10px;">⬤ {status_label}</span><br>'
                    f'<span style="color:#8b949e;font-size:0.85rem;">'
                    f'{meta["description"]}</span>'
                    f'{"<br><code style=color:#8b949e;font-size:0.78rem>Example: " + meta["example"] + "</code>" if meta["example"] else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with col_toggle:
                if st.button(
                    "Disable" if enabled else "Enable",
                    key=f"toggle_{name}",
                    type="secondary" if enabled else "primary",
                    use_container_width=True,
                ):
                    toggle_tool(name)
                    st.rerun()

        st.markdown("---")

    # ── Summary bar ───────────────────────────────────────────────────────────
    total    = len(tools)
    enabled  = sum(1 for n in tools if is_tool_enabled(n))
    disabled = total - enabled

    c1, c2, c3 = st.columns(3)
    c1.metric("Total",    total)
    c2.metric("✅ Enabled",  enabled)
    c3.metric("⏸ Disabled", disabled)


# ── Test tool ─────────────────────────────────────────────────────────────────

def _section_test(tools: dict) -> None:
    st.subheader("🧪 Test a Tool")

    enabled_tools = {n: t for n, t in tools.items() if is_tool_enabled(n)}
    if not enabled_tools:
        st.warning("No tools are currently enabled.")
        return

    tool_name = st.selectbox(
        "Select tool",
        list(enabled_tools.keys()),
        key="test_tool_select",
    )

    meta = _TOOL_META.get(tool_name, _DEFAULT_META)
    query = st.text_input(
        "Query",
        placeholder=meta.get("example", "Enter query..."),
        key="test_tool_query",
    )

    if st.button("▶ Run", key="test_tool_run", type="primary"):
        if not query.strip():
            st.warning("Please enter a query.")
            return

        with st.spinner(f"Running `{tool_name}`..."):
            try:
                result = enabled_tools[tool_name].execute(query.strip())
                st.success("✅ Tool executed successfully.")
                st.code(str(result), language="text")
            except Exception as exc:
                st.error(f"❌ Tool failed: {exc}")


# ── Health check ──────────────────────────────────────────────────────────────

def _section_health(tools: dict) -> None:
    st.subheader("❤️ Tool Health Check")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "Run a quick test query against each tool to verify it's working.</p>",
        unsafe_allow_html=True,
    )

    if st.button("🔍 Run all health checks", key="health_run_all", type="primary"):
        for name, tool in tools.items():
            meta    = _TOOL_META.get(name, _DEFAULT_META)
            health_q = meta.get("health_q", "")
            enabled  = is_tool_enabled(name)

            col_name, col_result = st.columns([3, 7])
            col_name.markdown(
                f'{meta["icon"]} **`{name}`** '
                f'{"" if enabled else "*(disabled)*"}',
            )

            if not enabled:
                col_result.markdown(
                    '<span style="color:#8b949e;">⏸ Skipped (disabled)</span>',
                    unsafe_allow_html=True,
                )
                continue

            if not health_q:
                col_result.markdown(
                    '<span style="color:#8b949e;">— No health query defined</span>',
                    unsafe_allow_html=True,
                )
                continue

            try:
                result = tool.execute(health_q)
                if result:
                    col_result.markdown(
                        f'<span style="color:#56d364;">✅ OK — '
                        f'{str(result)[:60]}</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    col_result.markdown(
                        '<span style="color:#e3b341;">⚠️ Empty response</span>',
                        unsafe_allow_html=True,
                    )
            except Exception as exc:
                col_result.markdown(
                    f'<span style="color:#f85149;">❌ {str(exc)[:80]}</span>',
                    unsafe_allow_html=True,
                )
