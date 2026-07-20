"""
ui/app.py

IRIS Streamlit Application — main entry point.

Run with:
    streamlit run ui/app.py

Flow:
    Browser → Streamlit → IrisAssistant (via AutonomousAgent)
    The UI never bypasses the agent pipeline.

Architecture:
    app.py          ← you are here (page config, routing)
    components/     ← reusable UI widgets
    pages/          ← one module per page (Chat, Memory, Workflow, Tools, Settings)
    utils/session   ← st.session_state helpers + Container cache
    utils/theme     ← CSS injection
"""

import sys
import os

# ── Make the project root importable from ui/app.py ──────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from ui.utils.theme   import inject_css
from ui.utils.session import get_active_page
from ui.components.sidebar import render_sidebar

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title     = "IRIS — Intelligent Reasoning Information System",
    page_icon      = "🤖",
    layout         = "wide",
    initial_sidebar_state = "expanded",
)

# ── Global styles ─────────────────────────────────────────────────────────────
inject_css()

# ── Sidebar (navigation + status) ────────────────────────────────────────────
selected_page = render_sidebar()

# ── Page routing ──────────────────────────────────────────────────────────────
if selected_page == "Chat":
    from ui.pages.chat import render
    render()

elif selected_page == "Memory":
    from ui.pages.memory import render
    render()

elif selected_page == "Workflow":
    from ui.pages.workflow import render
    render()

elif selected_page == "Tools":
    from ui.pages.tools import render
    render()

elif selected_page == "Settings":
    from ui.pages.settings import render
    render()
