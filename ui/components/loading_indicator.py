"""
ui/components/loading_indicator.py

Improvements 2 & 4 — Thinking Animation + Agent Activity Panel.

Shows a live multi-stage pipeline while the agent works:

    🧠 Planning...
    ⚙ Executing...
    💭 Generating response...

And an activity panel with checkmarks as each stage completes:

    🧠 Planner      ✔ Created Plan
    ⚙  Calculator   ✔ Finished
    💾 Memory        Updating...
"""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st


# ── Stage labels ──────────────────────────────────────────────────────────────

STAGE_THINKING   = "🧠 Planning..."
STAGE_MEMORY     = "🔍 Searching memory..."
STAGE_PLANNING   = "📋 Creating plan..."
STAGE_EXECUTING  = "⚙️ Executing..."
STAGE_GENERATING = "💭 Generating response..."
STAGE_REFLECTING = "🔄 Reflecting..."
STAGE_SAVING     = "💾 Saving to memory..."
STAGE_DONE       = "✅ Response ready"

# Ordered pipeline for the activity panel
PIPELINE_STAGES = [
    ("🧠", "Planner",    STAGE_PLANNING),
    ("⚙️",  "Executor",   STAGE_EXECUTING),
    ("🔄", "Reflection", STAGE_REFLECTING),
    ("💾", "Memory",     STAGE_SAVING),
    ("💭", "LLM",        STAGE_GENERATING),
]


# ── ThinkingIndicator — inline animated stage ─────────────────────────────────

class ThinkingIndicator:
    """
    Shows a single animated stage label that updates as processing moves forward.
    Call update(stage) to advance, clear() when done.
    """

    def __init__(self) -> None:
        self._slot = st.empty()

    def update(self, stage: str) -> None:
        self._slot.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;'
            f'background:#161b22;border:1px solid #30363d;border-radius:10px;'
            f'padding:10px 16px;margin:6px 0;font-size:0.9rem;">'
            f'<span style="display:inline-block;animation:spin 0.8s linear infinite;">⟳</span>'
            f'<span style="color:#8b949e;">{stage}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    def clear(self) -> None:
        self._slot.empty()


# ── ActivityPanel — full pipeline with checkmarks ────────────────────────────

class ActivityPanel:
    """
    Improvement 4 — Agent Activity Panel.

    Shows the full pipeline with live status:
        🧠 Planner      ✔ Created Plan
        ⚙  Calculator   ✔ Finished
        💾 Memory        Updating...

    Usage:
        panel = ActivityPanel()
        panel.start("🧠", "Planner", "Planning...")
        ...
        panel.complete("🧠", "Planner", "Created plan ✔")
        panel.start("⚙️", "Executor", "Running tool...")
        ...
        panel.close()
    """

    def __init__(self) -> None:
        self._slot   = st.empty()
        self._stages: list[dict] = []

    def start(self, icon: str, name: str, detail: str = "") -> None:
        """Mark a stage as currently running."""
        # Remove existing entry for this name if present
        self._stages = [s for s in self._stages if s["name"] != name]
        self._stages.append({"icon": icon, "name": name, "detail": detail, "done": False})
        self._render()

    def complete(self, name: str, detail: str = "") -> None:
        """Mark a stage as completed."""
        for s in self._stages:
            if s["name"] == name:
                s["done"]   = True
                s["detail"] = detail
        self._render()

    def close(self) -> None:
        """Remove the panel."""
        self._slot.empty()

    def _render(self) -> None:
        rows = []
        for s in self._stages:
            if s["done"]:
                icon_html = f'<span style="color:#56d364;font-weight:600;">✔</span>'
                color     = "#56d364"
            else:
                icon_html = f'<span style="display:inline-block;animation:spin 0.9s linear infinite;color:#e3b341;">⟳</span>'
                color     = "#e3b341"

            rows.append(
                f'<div style="display:flex;align-items:center;gap:8px;'
                f'padding:4px 0;border-bottom:1px solid #21262d;">'
                f'<span style="width:20px;text-align:center;">{s["icon"]}</span>'
                f'<span style="min-width:80px;font-weight:600;color:#e0e0e0;">{s["name"]}</span>'
                f'{icon_html}'
                f'<span style="color:{color};font-size:0.82rem;">{s["detail"]}</span>'
                f'</div>'
            )

        self._slot.markdown(
            f'<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;'
            f'padding:10px 14px;margin:6px 0;">'
            f'<div style="font-size:0.75rem;color:#8b949e;margin-bottom:6px;font-weight:600;">'
            f'CURRENT ACTIVITY</div>'
            + "".join(rows)
            + "</div>",
            unsafe_allow_html=True,
        )


# ── Simple context-manager wrapper ────────────────────────────────────────────

@contextmanager
def thinking_context(label: str = STAGE_THINKING):
    """One-liner context manager for simple blocking calls."""
    indicator = ThinkingIndicator()
    indicator.update(label)
    try:
        yield indicator
    finally:
        indicator.clear()


# ── CSS ───────────────────────────────────────────────────────────────────────

THINKING_CSS = """
<style>
@keyframes spin {
    0%   { transform: rotate(0deg);   }
    100% { transform: rotate(360deg); }
}
.thinking-dot {
    width: 8px; height: 8px;
    background: #1f6feb;
    border-radius: 50%;
    animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1;   transform: scale(1);   }
    50%       { opacity: 0.4; transform: scale(0.7); }
}
</style>
"""
