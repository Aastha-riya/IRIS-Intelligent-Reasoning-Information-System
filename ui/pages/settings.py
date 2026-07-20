"""
ui/pages/settings.py

Settings page — view and edit IRIS configuration.
"""

import streamlit as st

from ui.components.header import render_header
from ui.components.status import info as show_info
from ui.utils.session     import get_container
import config.settings as cfg


def render() -> None:
    render_header("Settings", "IRIS configuration and system info")

    st.subheader("🤖 Model")
    col1, col2 = st.columns(2)
    col1.text_input("Model name",       value=cfg.DEFAULT_MODEL,   disabled=True)
    col2.text_input("Temperature",      value=str(cfg.LLM_TEMPERATURE), disabled=True)

    st.subheader("🧠 Memory")
    col3, col4, col5 = st.columns(3)
    col3.number_input("Max history turns",    value=cfg.MAX_HISTORY,         disabled=True)
    col4.number_input("Context history",      value=cfg.MAX_CONTEXT_HISTORY,  disabled=True)
    col5.number_input("Context memories",     value=cfg.MAX_CONTEXT_MEMORIES, disabled=True)

    st.subheader("⚙️ Executor / Reflection")
    col6, col7, col8 = st.columns(3)
    col6.number_input("Max task retries",     value=cfg.MAX_TASK_RETRIES,         disabled=True)
    col7.number_input("Max replan attempts",  value=cfg.MAX_REPLAN_ATTEMPTS,      disabled=True)
    col8.number_input("Max workflow cycles",  value=cfg.MAX_WORKFLOW_CYCLES,      disabled=True)

    st.divider()
    show_info(
        "Settings are read from config/settings.py. "
        "Edit that file to change values — restart IRIS to apply."
    )

    st.divider()
    st.subheader("📊 System Info")
    try:
        container = get_container()
        st.json({
            "agent_status":    container.agent.status.value,
            "tools":           list(container.tool_manager.tools.keys()),
            "model":           cfg.DEFAULT_MODEL,
            "history_file":    cfg.HISTORY_FILE,
            "vector_index":    cfg.VECTOR_INDEX_FILE,
            "log_file":        cfg.LOG_FILE,
        })
    except Exception as exc:
        st.markdown(f"System info unavailable: {exc}")
