"""
ui/utils/theme.py

CSS injection for the IRIS Streamlit UI.
Dark theme with rounded chat bubbles, custom scrollbar, and agent colours.
"""

DARK_CSS = """
<style>
/* ── Base ─────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0e1117;
    color: #e0e0e0;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}
[data-testid="stSidebar"] .stMarkdown p {
    color: #8b949e;
    font-size: 0.8rem;
}

/* ── Chat bubbles ─────────────────────────────────────────────────────── */
.user-bubble {
    background: linear-gradient(135deg, #1f6feb, #388bfd);
    color: #ffffff;
    border-radius: 18px 18px 4px 18px;
    padding: 10px 16px;
    margin: 6px 0 6px 20%;
    max-width: 80%;
    word-wrap: break-word;
    box-shadow: 0 2px 8px rgba(31,111,235,0.3);
}
.iris-bubble {
    background: #21262d;
    color: #e0e0e0;
    border: 1px solid #30363d;
    border-radius: 18px 18px 18px 4px;
    padding: 10px 16px;
    margin: 6px 20% 6px 0;
    max-width: 80%;
    word-wrap: break-word;
}
.iris-bubble code {
    background: #161b22;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 0.88rem;
    color: #79c0ff;
}
.iris-bubble pre {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px;
    overflow-x: auto;
}

/* ── Decision badge ───────────────────────────────────────────────────── */
.decision-badge {
    display: inline-block;
    font-size: 0.68rem;
    padding: 2px 8px;
    border-radius: 10px;
    margin-top: 4px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.badge-direct  { background: #1f6feb22; color: #79c0ff; border: 1px solid #1f6feb; }
.badge-tool    { background: #2ea04322; color: #56d364; border: 1px solid #2ea043; }
.badge-plan    { background: #bb800922; color: #e3b341; border: 1px solid #bb8009; }
.badge-clarify { background: #6e40c922; color: #d2a8ff; border: 1px solid #6e40c9; }

/* ── Status indicators ────────────────────────────────────────────────── */
.status-online  { color: #56d364; font-weight: 600; }
.status-offline { color: #f85149; font-weight: 600; }
.status-idle    { color: #8b949e; font-weight: 600; }

/* ── Input box ────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 10px;
    color: #e0e0e0;
    padding: 10px 14px;
}
[data-testid="stTextInput"] input:focus {
    border-color: #1f6feb;
    box-shadow: 0 0 0 3px rgba(31,111,235,0.2);
}

/* ── Buttons ──────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #1f6feb, #388bfd);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 8px 20px;
    font-weight: 600;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }

/* ── Scrollbar ────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0e1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }

/* ── Metric cards ─────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px;
}
</style>
"""


def inject_css() -> None:
    """Call this once at the top of every page to apply the IRIS dark theme."""
    import streamlit as st
    from ui.components.loading_indicator import THINKING_CSS
    st.markdown(DARK_CSS + THINKING_CSS, unsafe_allow_html=True)
