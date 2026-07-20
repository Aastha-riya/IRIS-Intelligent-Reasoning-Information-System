"""
ui/pages/logs.py

Logging Dashboard — Step 5.

Displays:
    - Live log viewer from logs/iris.log
    - Filter by level (DEBUG / INFO / WARNING / ERROR)
    - Search within logs
    - Download log file
    - Auto-refresh toggle
    - Log statistics (counts per level)
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

import config.settings as cfg


# ── Log level colours ─────────────────────────────────────────────────────────

_LEVEL_COLOR = {
    "DEBUG":    "#8b949e",
    "INFO":     "#79c0ff",
    "WARNING":  "#e3b341",
    "ERROR":    "#f85149",
    "CRITICAL": "#ff0000",
}

_LEVEL_ICON = {
    "DEBUG":    "🔵",
    "INFO":     "ℹ️",
    "WARNING":  "⚠️",
    "ERROR":    "❌",
    "CRITICAL": "🚨",
}


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("## 📋 Log Dashboard")
    st.markdown(
        '<p style="color:#8b949e;">Real-time logs from <code>logs/iris.log</code>.</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    log_path = Path(cfg.LOG_FILE)

    if not log_path.exists():
        st.info("No log file found yet. Logs will appear here after IRIS starts processing requests.")
        return

    # ── Controls ──────────────────────────────────────────────────────────────
    col_filter, col_search, col_lines, col_refresh = st.columns([3, 4, 2, 2])

    with col_filter:
        level_filter = st.multiselect(
            "Level",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=["INFO", "WARNING", "ERROR", "CRITICAL"],
            key="log_level_filter",
            label_visibility="collapsed",
        )

    with col_search:
        search_q = st.text_input(
            "Search logs",
            placeholder="Search log content...",
            key="log_search",
            label_visibility="collapsed",
        )

    with col_lines:
        max_lines = st.selectbox(
            "Lines",
            [100, 250, 500, 1000],
            index=0,
            key="log_max_lines",
            label_visibility="collapsed",
        )

    with col_refresh:
        if st.button("🔄 Refresh", key="log_refresh", use_container_width=True):
            st.rerun()

    st.divider()

    # ── Read and filter logs ──────────────────────────────────────────────────
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as exc:
        st.error(f"Could not read log file: {exc}")
        return

    # Parse into structured entries
    entries = _parse_lines(all_lines)

    # Filter by level
    if level_filter:
        entries = [e for e in entries if e["level"] in level_filter]

    # Filter by search
    if search_q:
        entries = [e for e in entries if search_q.lower() in e["raw"].lower()]

    # Most recent first
    entries = list(reversed(entries))[-max_lines:]

    # ── Statistics ────────────────────────────────────────────────────────────
    _render_stats(all_lines)

    st.divider()

    # ── Log lines ─────────────────────────────────────────────────────────────
    st.caption(f"Showing {len(entries)} of {len(all_lines)} lines.")

    if not entries:
        st.info("No log entries match the current filters.")
        return

    log_html = []
    for e in entries:
        color = _LEVEL_COLOR.get(e["level"], "#8b949e")
        icon  = _LEVEL_ICON.get(e["level"], "·")
        ts    = e["timestamp"]
        msg   = e["message"].replace("<", "&lt;").replace(">", "&gt;")
        log_html.append(
            f'<div style="font-family:monospace;font-size:0.8rem;'
            f'padding:3px 0;border-bottom:1px solid #21262d;">'
            f'<span style="color:#8b949e;">{ts}</span> '
            f'{icon} <span style="color:{color};font-weight:600;">{e["level"]:<8}</span> '
            f'<span style="color:#e0e0e0;">{msg}</span>'
            f'</div>'
        )

    st.markdown(
        '<div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;'
        'padding:12px 16px;max-height:500px;overflow-y:auto;">'
        + "".join(log_html)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Download ──────────────────────────────────────────────────────────────
    try:
        with open(log_path, "rb") as f:
            st.download_button(
                label     = "⬇ Download iris.log",
                data      = f,
                file_name = "iris.log",
                mime      = "text/plain",
                key       = "log_download",
            )
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_lines(lines: list[str]) -> list[dict]:
    """Parse log lines into structured dicts with timestamp, level, message."""
    entries = []
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        # Expected format: "2026-07-20 12:34:56 | LEVEL    | message"
        parts = line.split(" | ", 2)
        if len(parts) == 3:
            ts, level, message = parts
            entries.append({
                "timestamp": ts.strip(),
                "level":     level.strip(),
                "message":   message.strip(),
                "raw":       line,
            })
        else:
            entries.append({
                "timestamp": "",
                "level":     "INFO",
                "message":   line,
                "raw":       line,
            })
    return entries


def _render_stats(all_lines: list[str]) -> None:
    """Render level-count metrics."""
    counts = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    for line in all_lines:
        for level in counts:
            if f"| {level}" in line or f"|{level}" in line:
                counts[level] += 1
                break

    cols = st.columns(5)
    cols[0].metric("DEBUG",    counts["DEBUG"])
    cols[1].metric("INFO",     counts["INFO"])
    cols[2].metric("⚠ WARNING", counts["WARNING"])
    cols[3].metric("❌ ERROR",   counts["ERROR"])
    cols[4].metric("🚨 CRITICAL", counts["CRITICAL"])
