"""
ui/components/system_info.py

System information panel — Step 9.
Displays: model, memory usage, CPU, RAM, uptime, tools, conversations.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import streamlit as st


# ── Session uptime tracker ────────────────────────────────────────────────────

def _get_uptime() -> str:
    """Return session uptime as a human-readable string."""
    if "session_start" not in st.session_state:
        st.session_state["session_start"] = time.time()
    elapsed = int(time.time() - st.session_state["session_start"])
    h, rem  = divmod(elapsed, 3600)
    m, s    = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


# ── Public API ────────────────────────────────────────────────────────────────

def render_system_info() -> None:
    """Render the full system information panel."""
    from ui.utils.session import get_container, list_conversations
    from ui.utils.prefs   import get_pref

    st.markdown("### 📊 System Information")

    # ── Model ─────────────────────────────────────────────────────────────────
    current_model = get_pref("model")
    st.markdown(f"**Active model:** `{current_model}`")

    # ── Resource metrics (psutil optional) ────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    try:
        import psutil
        proc    = psutil.Process(os.getpid())
        mem_mb  = proc.memory_info().rss / (1024 * 1024)
        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram_pct = psutil.virtual_memory().percent
        ram_gb  = psutil.virtual_memory().used / (1024 ** 3)

        col1.metric("🧠 Process RAM", f"{mem_mb:.0f} MB")
        col2.metric("💻 CPU",         f"{cpu_pct:.1f}%")
        col3.metric("🖥️ System RAM",  f"{ram_pct:.1f}%  ({ram_gb:.1f} GB)")
    except ImportError:
        col1.metric("🧠 RAM", "psutil not installed")
        col2.metric("💻 CPU", "—")
        col3.metric("🖥️ Sys", "—")

    col4.metric("⏱️ Uptime", _get_uptime())

    st.divider()

    # ── Tools ─────────────────────────────────────────────────────────────────
    col_tools, col_convs = st.columns(2)

    with col_tools:
        st.markdown("**Loaded tools**")
        try:
            tools = list(get_container().tool_manager.tools.keys())
            for t in tools:
                st.markdown(
                    f'<span style="color:#56d364;">⬤</span> `{t}`',
                    unsafe_allow_html=True,
                )
        except Exception:
            st.caption("Tools unavailable.")

    with col_convs:
        st.markdown("**Active conversations**")
        try:
            convs = list_conversations()
            st.metric("Total conversations", len(convs))
            total_msgs = sum(len(c["messages"]) for c in convs)
            st.metric("Total messages", total_msgs)
        except Exception:
            st.caption("Conversation data unavailable.")

    st.divider()

    # ── Memory subsystem ──────────────────────────────────────────────────────
    st.markdown("**Memory subsystem**")
    try:
        mm = get_container().memory_manager
        c1, c2 = st.columns(2)
        c1.metric("Conversation turns", len(mm._history))
        c2.metric("Vector store size",  mm._vector_store.size())
    except Exception:
        st.caption("Memory subsystem unavailable.")

    st.divider()

    # ── Environment ───────────────────────────────────────────────────────────
    import sys
    st.markdown("**Environment**")
    st.code(
        f"Python:     {sys.version.split()[0]}\n"
        f"Platform:   {sys.platform}\n"
        f"PID:        {os.getpid()}\n"
        f"Session:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        language="text",
    )
