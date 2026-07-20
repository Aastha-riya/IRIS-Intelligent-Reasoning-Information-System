"""
ui/app.py

IRIS Streamlit Application — v1.0 Production Entry Point.

Run with:
    streamlit run ui/app.py

Startup order:
    1. Add project root to sys.path
    2. Set Streamlit page config
    3. Load persistent user preferences from settings.json
    4. Inject base dark-theme CSS + dynamic appearance CSS
    5. Render sidebar
    6. Route to selected page
"""

import sys
import os

# ── Project root on sys.path ──────────────────────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

# ── Page config — must be the very first Streamlit call ───────────────────────
st.set_page_config(
    page_title            = "IRIS — Intelligent Reasoning Information System",
    page_icon             = "🤖",
    layout                = "wide",
    initial_sidebar_state = "expanded",
    menu_items={
        "Get help":    "https://github.com/your-username/IRIS",
        "Report a bug": "https://github.com/your-username/IRIS/issues",
        "About":       "IRIS v1.0 — Local AI Agent built with Ollama + Streamlit",
    },
)

# ── Load persistent preferences on first run ─────────────────────────────────
if "prefs" not in st.session_state:
    from ui.utils.prefs import load_prefs
    st.session_state["prefs"] = load_prefs()

# ── Track session start time for uptime display ───────────────────────────────
import time
if "session_start" not in st.session_state:
    st.session_state["session_start"] = time.time()

# ── Inject CSS ────────────────────────────────────────────────────────────────
from ui.utils.theme                import inject_css
from ui.components.settings_panel  import inject_appearance_css

inject_css()
inject_appearance_css()

# ── Sidebar ───────────────────────────────────────────────────────────────────
from ui.components.sidebar import render_sidebar

selected_page = render_sidebar()

# ── Page routing ──────────────────────────────────────────────────────────────
if selected_page == "Dashboard":
    from ui.pages.dashboard import render
    render()

elif selected_page == "Chat":
    from ui.pages.chat import render
    render()

elif selected_page == "Memory":
    from ui.pages.memory import render
    render()

elif selected_page == "Conversations":
    from ui.pages.conversations import render
    render()

elif selected_page == "Workflow":
    from ui.pages.workflow import render
    render()

elif selected_page == "Tools":
    from ui.pages.tools import render
    render()

elif selected_page == "Logs":
    from ui.pages.logs import render
    render()

elif selected_page == "Settings":
    from ui.pages.settings import render
    render()

else:
    # Fallback to Dashboard
    from ui.pages.dashboard import render
    render()
