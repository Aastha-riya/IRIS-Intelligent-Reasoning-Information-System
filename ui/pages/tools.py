"""
ui/pages/tools.py

Tools page — view registered tools and test them directly.
"""

import streamlit as st

from ui.components.header import render_header
from ui.components.status import error as show_error, success as show_success
from ui.utils.session     import get_container


def render() -> None:
    render_header("Tools", "Registered tools and direct test interface")

    try:
        container    = get_container()
        tool_manager = container.tool_manager
        tools        = tool_manager.tools
    except Exception as exc:
        show_error(f"ToolManager unavailable: {exc}")
        return

    # ── Tool cards ────────────────────────────────────────────────────────────
    st.subheader(f"📦 {len(tools)} Registered Tool(s)")

    _DESCRIPTIONS = {
        "calculator":     "Evaluates mathematical expressions.",
        "file_reader":    "Reads the contents of a file.",
        "project_scanner": "Scans a project directory for source files.",
        "internet":       "Searches the web using DuckDuckGo.",
    }

    for name in tools:
        with st.container():
            col1, col2 = st.columns([1, 9])
            col1.markdown("🔧")
            col2.markdown(
                f"**`{name}`**  \n"
                f'<span style="color:#8b949e;font-size:0.85rem;">'
                f'{_DESCRIPTIONS.get(name, "")}</span>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Direct tool test ──────────────────────────────────────────────────────
    st.subheader("🧪 Test a Tool")
    tool_choice = st.selectbox("Select tool", list(tools.keys()), key="tool_select")
    query = st.text_input(
        "Query",
        placeholder={
            "calculator":      "calculate 52 * 73",
            "file_reader":     "read README.md",
            "project_scanner": "scan .",
            "internet":        "search Python async tutorial",
        }.get(tool_choice, "Enter your query"),
        key="tool_query",
    )

    if st.button("▶ Run Tool", key="run_tool"):
        if not query.strip():
            show_error("Please enter a query.")
            return

        with st.spinner(f"Running {tool_choice}..."):
            try:
                tool   = tools[tool_choice]
                result = tool.execute(query.strip())
                show_success("Tool executed successfully.")
                st.code(str(result), language="text")
            except Exception as exc:
                show_error(f"Tool failed: {exc}")
