"""
ui/components/loading_indicator.py

Loading / thinking indicator for the IRIS chat UI.

Shows the user what stage the agent is currently in:

    🧠 Thinking...       ← initial reasoning
    🔍 Searching memory  ← observe phase
    📋 Planning...       ← planner running
    ⚙️  Executing...      ← executor running
    🔄 Reflecting...     ← reflection engine
    ✅ Response ready    ← done

Usage:
    with thinking_context("🧠 Thinking..."):
        result = agent.run(prompt)

    Or for manual control:
        indicator = ThinkingIndicator()
        indicator.update("📋 Planning...")
        ...
        indicator.clear()
"""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st


# ── Stage labels ──────────────────────────────────────────────────────────────

STAGE_THINKING  = "🧠 Thinking..."
STAGE_MEMORY    = "🔍 Searching memory..."
STAGE_PLANNING  = "📋 Planning..."
STAGE_EXECUTING = "⚙️ Executing..."
STAGE_REFLECTING = "🔄 Reflecting..."
STAGE_DONE      = "✅ Response ready"


# ── Simple spinner wrapper ────────────────────────────────────────────────────

@contextmanager
def thinking_context(label: str = STAGE_THINKING):
    """
    Context manager that shows a styled thinking indicator while the
    enclosed block runs.

    Usage:
        with thinking_context("📋 Planning..."):
            result = agent.run(prompt)
    """
    placeholder = st.empty()
    placeholder.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;'
        f'color:#8b949e;font-size:0.9rem;padding:8px 0;">'
        f'<div class="thinking-dot"></div>{label}</div>',
        unsafe_allow_html=True,
    )
    try:
        yield placeholder
    finally:
        placeholder.empty()


# ── Multi-stage indicator ─────────────────────────────────────────────────────

class ThinkingIndicator:
    """
    Multi-stage thinking indicator.
    Call update() as the agent progresses through stages.
    Call clear() when done.

    Usage:
        indicator = ThinkingIndicator()
        indicator.update(STAGE_PLANNING)
        plan = planner.create_plan(goal)
        indicator.update(STAGE_EXECUTING)
        result = executor.run(plan)
        indicator.clear()
    """

    def __init__(self) -> None:
        self._slot = st.empty()

    def update(self, stage: str) -> None:
        """Show the given stage label in the indicator slot."""
        self._slot.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'background:#21262d;border:1px solid #30363d;border-radius:10px;'
            f'padding:10px 16px;color:#8b949e;font-size:0.88rem;">'
            f'<span style="animation:spin 1s linear infinite;'
            f'display:inline-block;">⟳</span> {stage}</div>',
            unsafe_allow_html=True,
        )

    def clear(self) -> None:
        """Remove the indicator."""
        self._slot.empty()


# ── CSS for animation (injected via theme.py) ─────────────────────────────────

THINKING_CSS = """
<style>
@keyframes spin {
    0%   { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
.thinking-dot {
    width: 8px; height: 8px;
    background: #1f6feb;
    border-radius: 50%;
    animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1);   }
    50%       { opacity: 0.4; transform: scale(0.7); }
}
</style>
"""
