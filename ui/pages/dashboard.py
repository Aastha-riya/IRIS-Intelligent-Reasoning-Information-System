"""
ui/pages/dashboard.py

Improvements 7 & 8 — Real homepage + Workflow Visualization.

Sections:
    - Hero banner with live agent/model/status
    - Today's activity: conversations, messages, memories
    - System health: Ollama, CPU, RAM, uptime
    - Workflow visualization panel (always visible)
    - Recent conversations with open buttons
    - Quick actions + Sample prompts
"""

from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

from ui.utils.session import (
    get_container, list_conversations, switch_conv, set_active_page, new_conv,
)
from ui.utils.prefs import get_pref


# ── Sample prompts ────────────────────────────────────────────────────────────

SAMPLE_PROMPTS = [
    {"label": "💻 Code Review",   "prompt": "Review this Python code for improvements: def add(a,b): return a+b"},
    {"label": "📄 Summarise File","prompt": "Summarize the README.md file for me"},
    {"label": "🔢 Math",          "prompt": "calculate 15% of 2400"},
    {"label": "🔍 Scan Project",  "prompt": "scan ."},
    {"label": "🤖 What is IRIS?", "prompt": "What are your capabilities?"},
    {"label": "🧠 Explain ML",    "prompt": "Explain neural networks in simple terms"},
    {"label": "📊 CSV Help",      "prompt": "How do I read a CSV file in Python?"},
    {"label": "🛠️ Debug Help",    "prompt": "Why does Python raise a RecursionError?"},
]


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:

    # ── Hero ──────────────────────────────────────────────────────────────────
    _render_hero()
    st.divider()

    # ── Today's activity + System health ─────────────────────────────────────
    col_activity, col_health = st.columns([5, 5], gap="large")
    with col_activity:
        _render_today_activity()
    with col_health:
        _render_system_health()

    st.divider()

    # ── Improvement 8: Workflow Visualization ─────────────────────────────────
    _render_workflow_visualization()

    st.divider()

    # ── Recent conversations + Quick actions ──────────────────────────────────
    col_left, col_right = st.columns([5, 5], gap="large")
    with col_left:
        _render_recent_conversations()
    with col_right:
        _render_quick_actions()

    st.divider()

    # ── Sample prompts ────────────────────────────────────────────────────────
    _render_sample_prompts()


# ── Hero ──────────────────────────────────────────────────────────────────────

def _render_hero() -> None:
    model        = get_pref("model") or "llama3.2"
    ollama_ok    = _check_ollama()
    status_label = "Online" if ollama_ok else "Offline"
    status_color = "#56d364" if ollama_ok else "#f85149"

    try:
        container    = get_container()
        agent_status = container.agent.status.value
        a_color      = {"idle": "#56d364", "running": "#e3b341"}.get(agent_status, "#8b949e")
    except Exception:
        agent_status = "offline"
        a_color      = "#f85149"

    st.markdown(
        f'<div style="background:linear-gradient(135deg,#161b22,#21262d);'
        f'border:1px solid #30363d;border-radius:14px;padding:28px 32px;'
        f'display:flex;align-items:center;justify-content:space-between;">'

        f'<div style="display:flex;align-items:center;gap:16px;">'
        f'<div style="font-size:3rem;">🤖</div>'
        f'<div>'
        f'<div style="font-size:1.6rem;font-weight:800;letter-spacing:-0.5px;">IRIS</div>'
        f'<div style="color:#8b949e;font-size:0.85rem;">Intelligent Reasoning Information System · v1.0</div>'
        f'</div>'
        f'</div>'

        f'<div style="display:flex;gap:12px;align-items:center;">'
        f'<div style="background:#21262d;border:1px solid #30363d;border-radius:10px;'
        f'padding:8px 14px;font-size:0.82rem;">'
        f'<span style="color:#8b949e;">Model </span>'
        f'<code style="color:#79c0ff;">{model}</code>'
        f'</div>'
        f'<div style="background:{a_color}22;border:1px solid {a_color};border-radius:10px;'
        f'padding:8px 14px;font-size:0.82rem;font-weight:600;color:{a_color};">'
        f'⬤ Agent {agent_status.title()}'
        f'</div>'
        f'<div style="background:{status_color}22;border:1px solid {status_color};border-radius:10px;'
        f'padding:8px 14px;font-size:0.82rem;font-weight:600;color:{status_color};">'
        f'⬤ Ollama {status_label}'
        f'</div>'
        f'</div>'

        f'</div>',
        unsafe_allow_html=True,
    )


# ── Today's activity ──────────────────────────────────────────────────────────

def _render_today_activity() -> None:
    st.markdown("#### 📅 Today's Activity")
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        convs         = list_conversations()
        today_convs   = [c for c in convs if c["created"].startswith(today)]
        today_msgs    = sum(
            len([m for m in c["messages"] if m.get("timestamp", "").startswith(today)])
            for c in convs
        )
        total_convs   = len(convs)

        mm            = get_container().memory_manager
        total_vectors = mm._vector_store.size()
        total_turns   = len(mm._history)
    except Exception:
        today_convs   = []
        today_msgs    = 0
        total_convs   = 0
        total_vectors = 0
        total_turns   = 0

    cols = st.columns(3)
    cols[0].metric("New Chats Today",    len(today_convs))
    cols[1].metric("Messages Today",     today_msgs)
    cols[2].metric("Total Memories",     total_vectors)

    cols2 = st.columns(3)
    cols2[0].metric("Total Chats",       total_convs)
    cols2[1].metric("History Turns",     total_turns)
    cols2[2].metric("Session",           _uptime())


# ── System health ─────────────────────────────────────────────────────────────

def _render_system_health() -> None:
    st.markdown("#### 🩺 System Health")

    checks = []

    # Ollama
    ok = _check_ollama()
    checks.append(("🤖 Ollama",   ok,    "Connected" if ok else "Not running"))

    # Memory subsystem
    try:
        mm = get_container().memory_manager
        checks.append(("💾 Memory",  True, f"{mm._vector_store.size()} vectors"))
    except Exception as e:
        checks.append(("💾 Memory",  False, str(e)[:40]))

    # Tools
    try:
        from ui.utils.prefs import is_tool_enabled
        tools   = get_container().tool_manager.tools
        enabled = [t for t in tools if is_tool_enabled(t)]
        checks.append(("🔧 Tools",   True, f"{len(enabled)}/{len(tools)} active"))
    except Exception:
        checks.append(("🔧 Tools",   False, "Unavailable"))

    # CPU / RAM
    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=0.05)
        ram  = psutil.virtual_memory().percent
        checks.append(("💻 CPU/RAM", cpu < 90 and ram < 90,
                        f"CPU {cpu:.0f}% · RAM {ram:.0f}%"))
    except ImportError:
        checks.append(("💻 CPU/RAM", None, "psutil not installed"))

    for label, ok, detail in checks:
        if ok is True:
            color, dot = "#56d364", "✅"
        elif ok is False:
            color, dot = "#f85149", "❌"
        else:
            color, dot = "#8b949e", "—"
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'background:#21262d;border:1px solid #30363d;border-radius:8px;'
            f'padding:7px 12px;margin-bottom:5px;font-size:0.84rem;">'
            f'<span>{label}</span>'
            f'<span style="color:{color};">{dot} {detail}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Improvement 8: Workflow Visualization ─────────────────────────────────────

def _render_workflow_visualization() -> None:
    st.markdown("#### 🔄 How IRIS Works — The Pipeline")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;margin-top:-8px;">'
        "Every request flows through this pipeline. Multi-step goals use all stages.</p>",
        unsafe_allow_html=True,
    )

    stages = [
        ("🧑 User",        "You ask anything",                  "#79c0ff"),
        ("🧠 Reason",      "Decide: Direct / Tool / Plan",      "#d2a8ff"),
        ("📋 Plan",        "Decompose into tasks",              "#e3b341"),
        ("⚙️ Execute",      "Run tools in dependency order",    "#56d364"),
        ("🔄 Reflect",     "Evaluate, retry or replan",         "#f0883e"),
        ("💾 Memory",      "Store result in semantic memory",   "#79c0ff"),
        ("💭 Respond",     "Generate natural language reply",   "#56d364"),
    ]

    # Horizontal pipeline
    cols = st.columns(len(stages))
    for i, (icon, label, color) in enumerate(stages):
        with cols[i]:
            st.markdown(
                f'<div style="text-align:center;">'
                f'<div style="background:{color}22;border:1px solid {color};'
                f'border-radius:10px;padding:10px 6px;">'
                f'<div style="font-size:1.3rem;">{icon}</div>'
                f'<div style="font-size:0.72rem;font-weight:600;color:{color};'
                f'margin-top:4px;">{label}</div>'
                f'</div>'
                + (f'<div style="font-size:1rem;color:#30363d;margin-top:4px;">▶</div>'
                   if i < len(stages) - 1 else "")
                + f'</div>',
                unsafe_allow_html=True,
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
            '<div style="background:#21262d;border:1px solid #30363d;'
            'border-radius:10px;padding:24px;text-align:center;color:#8b949e;">'
            '🗨️<br><small>No conversations yet. Start chatting!</small></div>',
            unsafe_allow_html=True,
        )
        if st.button("💬 Start your first chat", key="dash_first_chat",
                     use_container_width=True, type="primary"):
            new_conv()
            set_active_page("Chat")
            st.rerun()
        return

    for conv in convs[:5]:
        msgs     = len(conv["messages"])
        pin_icon = "📌 " if conv.get("pinned") else ""
        last_ts  = conv["created"][:10]
        col_a, col_b = st.columns([8, 2])
        col_a.markdown(
            f'<div style="background:#21262d;border:1px solid #30363d;'
            f'border-radius:8px;padding:8px 12px;margin-bottom:4px;">'
            f'<strong>{pin_icon}{conv["name"][:35]}</strong>'
            f'<span style="color:#8b949e;font-size:0.76rem;">'
            f' · {msgs} msg · {last_ts}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if col_b.button("Open →", key=f"dash_open_{conv['id']}", use_container_width=True):
            switch_conv(conv["id"])
            set_active_page("Chat")
            st.rerun()


# ── Quick actions ─────────────────────────────────────────────────────────────

def _render_quick_actions() -> None:
    st.markdown("#### ⚡ Quick Actions")
    actions = [
        ("💬 New Chat",      "new_chat"),
        ("🧠 View Memory",   "memory"),
        ("🔧 Test Tools",    "tools"),
        ("📋 Run Workflow",  "workflow"),
        ("📋 View Logs",     "logs"),
        ("⚙️ Settings",      "settings"),
    ]
    for label, action in actions:
        if st.button(label, key=f"dash_qa_{action}", use_container_width=True):
            if action == "new_chat":
                new_conv()
                set_active_page("Chat")
            else:
                page_map = {
                    "memory":   "Memory",
                    "tools":    "Tools",
                    "workflow": "Workflow",
                    "logs":     "Logs",
                    "settings": "Settings",
                }
                set_active_page(page_map.get(action, "Dashboard"))
            st.rerun()


# ── Sample prompts ────────────────────────────────────────────────────────────

def _render_sample_prompts() -> None:
    st.markdown("#### 🚀 Try a Sample Prompt")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.84rem;margin-top:-8px;">'
        "Click any to open chat with it pre-filled.</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for i, sp in enumerate(SAMPLE_PROMPTS):
        if cols[i % 4].button(sp["label"], key=f"sample_{i}", use_container_width=True):
            st.session_state["_pending_prompt"] = sp["prompt"]
            set_active_page("Chat")
            st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_ollama() -> bool:
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def _uptime() -> str:
    if "session_start" not in st.session_state:
        st.session_state["session_start"] = time.time()
    elapsed = int(time.time() - st.session_state["session_start"])
    h, r    = divmod(elapsed, 3600)
    m, s    = divmod(r, 60)
    return f"{h}h {m}m {s}s"
