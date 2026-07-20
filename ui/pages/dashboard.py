"""
ui/pages/dashboard.py

IRIS Dashboard — Step 1: Professional home page.

Displays:
    - Welcome screen with agent status
    - Current model and system health
    - Recent conversations quick-access
    - Quick action buttons (sample prompts)
    - Live metrics: memory turns, vectors, uptime
    - Ollama connectivity status
"""

from __future__ import annotations

import time

import streamlit as st

from ui.utils.session import get_container, list_conversations, switch_conv
from ui.utils.prefs   import get_pref


# ── Sample prompts (Step 9) ───────────────────────────────────────────────────

SAMPLE_PROMPTS: list[dict] = [
    {"label": "💻 Code Review",      "prompt": "Review this Python function for bugs and improvements: def add(a,b): return a+b"},
    {"label": "📄 File Summary",      "prompt": "Summarize the README.md file for me"},
    {"label": "🔢 Math Solver",       "prompt": "calculate 15% of 2,400"},
    {"label": "🔍 Project Scan",      "prompt": "scan ."},
    {"label": "🤖 What is IRIS?",     "prompt": "What are you capable of doing?"},
    {"label": "🧠 ML Explanation",    "prompt": "Explain neural networks in simple terms"},
    {"label": "📊 Data Analysis",     "prompt": "How do I read a CSV file in Python?"},
    {"label": "🛠️ Debug Help",        "prompt": "Why does Python raise a RecursionError?"},
]


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    """Render the IRIS dashboard home page."""

    # ── Hero banner ───────────────────────────────────────────────────────────
    st.markdown(
        '<div style="text-align:center;padding:40px 0 20px;">'
        '<div style="font-size:3.5rem;">🤖</div>'
        '<h1 style="margin:10px 0 4px;font-size:2rem;">IRIS</h1>'
        '<p style="color:#8b949e;font-size:1rem;margin:0;">'
        'Intelligent Reasoning Information System</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── System health row ─────────────────────────────────────────────────────
    _render_health_row()

    st.divider()

    # ── Main content: recent convs + quick actions ────────────────────────────
    col_left, col_right = st.columns([5, 5], gap="large")

    with col_left:
        _render_recent_conversations()

    with col_right:
        _render_quick_actions()

    st.divider()

    # ── Sample prompts ────────────────────────────────────────────────────────
    _render_sample_prompts()


# ── Health row ────────────────────────────────────────────────────────────────

def _render_health_row() -> None:
    col1, col2, col3, col4, col5 = st.columns(5)

    # Agent status
    try:
        container    = get_container()
        agent_status = container.agent.status.value
        color = {"idle": "#56d364", "running": "#e3b341",
                 "paused": "#8b949e", "stopped": "#f85149"}.get(agent_status, "#8b949e")
        col1.markdown(
            f'<div class="dashboard-card">'
            f'<div style="font-size:0.75rem;color:#8b949e;">Agent</div>'
            f'<div style="font-size:1.1rem;font-weight:600;color:{color};">⬤ {agent_status}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        col1.markdown(_card("Agent", "⬤ offline", "#f85149"))

    # Model
    model = get_pref("model") or "llama3.2"
    col2.markdown(_card("Model", f"`{model}`", "#79c0ff"))

    # Ollama
    ollama_ok = _check_ollama_quick()
    col3.markdown(_card("Ollama", "✅ Connected" if ollama_ok else "❌ Offline",
                        "#56d364" if ollama_ok else "#f85149"))

    # Memory
    try:
        mm = get_container().memory_manager
        col4.markdown(_card("Memory", f"{len(mm._history)} turns · {mm._vector_store.size()} vectors", "#e3b341"))
    except Exception:
        col4.markdown(_card("Memory", "—", "#8b949e"))

    # Uptime
    if "session_start" not in st.session_state:
        st.session_state["session_start"] = time.time()
    elapsed = int(time.time() - st.session_state["session_start"])
    h, r = divmod(elapsed, 3600)
    m, s = divmod(r, 60)
    col5.markdown(_card("Uptime", f"{h}h {m}m {s}s", "#d2a8ff"))


def _card(label: str, value: str, color: str) -> str:
    return (
        f'<div style="background:#21262d;border:1px solid #30363d;border-radius:10px;'
        f'padding:12px 16px;">'
        f'<div style="font-size:0.72rem;color:#8b949e;margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:0.95rem;font-weight:600;color:{color};">{value}</div>'
        f'</div>'
    )


# ── Recent conversations ──────────────────────────────────────────────────────

def _render_recent_conversations() -> None:
    st.markdown("#### 💬 Recent Conversations")
    try:
        convs = list_conversations()
    except Exception:
        convs = []

    if not convs:
        st.markdown(
            '<div style="background:#21262d;border:1px solid #30363d;border-radius:10px;'
            'padding:20px;text-align:center;color:#8b949e;">'
            '🗨️<br>No conversations yet.<br>'
            '<small>Start chatting to see your history here.</small></div>',
            unsafe_allow_html=True,
        )
        return

    for conv in convs[:5]:
        msgs     = len(conv["messages"])
        pin_icon = "📌 " if conv.get("pinned") else ""
        col_a, col_b = st.columns([8, 2])
        col_a.markdown(
            f'<div style="background:#21262d;border:1px solid #30363d;'
            f'border-radius:8px;padding:8px 12px;">'
            f'<strong>{pin_icon}{conv["name"][:35]}</strong>'
            f'<span style="color:#8b949e;font-size:0.78rem;"> · {msgs} msg · {conv["created"][:10]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if col_b.button("Open", key=f"dash_open_{conv['id']}", use_container_width=True):
            switch_conv(conv["id"])
            from ui.utils.session import set_active_page
            set_active_page("Chat")
            st.rerun()


# ── Quick actions ─────────────────────────────────────────────────────────────

def _render_quick_actions() -> None:
    st.markdown("#### ⚡ Quick Actions")

    actions = [
        ("💬 New Chat",       "new_chat"),
        ("🧠 View Memory",    "memory"),
        ("🔧 Test Tools",     "tools"),
        ("⚙️ Settings",       "settings"),
        ("🔬 Diagnostics",    "diagnostics"),
    ]

    for label, action in actions:
        if st.button(label, key=f"dash_action_{action}", use_container_width=True):
            from ui.utils.session import new_conv, set_active_page
            if action == "new_chat":
                new_conv()
                set_active_page("Chat")
            elif action == "diagnostics":
                set_active_page("Settings")
            else:
                page_map = {
                    "memory":   "Memory",
                    "tools":    "Tools",
                    "settings": "Settings",
                }
                set_active_page(page_map.get(action, "Chat"))
            st.rerun()


# ── Sample prompts ────────────────────────────────────────────────────────────

def _render_sample_prompts() -> None:
    st.markdown("#### 🚀 Try a Sample Prompt")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;margin-top:-8px;">'
        "Click any prompt to open the chat with it pre-filled.</p>",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    for i, sp in enumerate(SAMPLE_PROMPTS):
        if cols[i % 4].button(sp["label"], key=f"sample_{i}", use_container_width=True):
            st.session_state["_pending_prompt"] = sp["prompt"]
            from ui.utils.session import set_active_page
            set_active_page("Chat")
            st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_ollama_quick() -> bool:
    """Quick non-blocking Ollama check — just imports the library."""
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False
