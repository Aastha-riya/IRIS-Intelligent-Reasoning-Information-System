"""
ui/components/workflow_panel.py

Workflow timeline panel — shows the user what the agent actually did.

Instead of hiding the agent's internal work, this panel reveals:
    Goal → Planning ✓ → Tool Selected ✓ → Executing ✓ → Reflection ✓ → Done ✓

Reads from a WorkflowResult or Plan object produced by the agent.
Renders a vertical timeline with per-task status indicators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from core.workflow import WorkflowResult
    from models.plan import Plan


# ── Status icons ──────────────────────────────────────────────────────────────

_TASK_ICON = {
    "completed": ("✅", "#56d364"),
    "failed":    ("❌", "#f85149"),
    "skipped":   ("⏭️",  "#8b949e"),
    "cancelled": ("🚫", "#f85149"),
    "running":   ("⚙️",  "#e3b341"),
    "pending":   ("○",  "#8b949e"),
    "waiting":   ("◔",  "#8b949e"),
}


# ── Public API ────────────────────────────────────────────────────────────────

def render_workflow_panel(workflow_result: WorkflowResult) -> None:
    """
    Render the full workflow timeline for a completed WorkflowResult.

    Args:
        workflow_result: A WorkflowResult from WorkflowEngine.run().
    """
    if workflow_result is None:
        return

    with st.expander(
        f"📋 Workflow — {workflow_result.status.value.upper()} "
        f"({workflow_result.cycles} cycle · {workflow_result.total_time:.2f}s)",
        expanded=False,
    ):
        # ── Summary bar ───────────────────────────────────────────────────────
        _render_summary_bar(workflow_result)

        # ── Task timeline ─────────────────────────────────────────────────────
        if workflow_result.plan and workflow_result.plan.tasks:
            st.markdown("**Task Timeline**")
            _render_task_timeline(workflow_result.plan)

        # ── Reflection summary ────────────────────────────────────────────────
        if workflow_result.reflection_summary:
            st.markdown("**Reflection**")
            st.markdown(
                f'<div style="background:#21262d;border:1px solid #30363d;'
                f'border-radius:8px;padding:10px 14px;color:#8b949e;'
                f'font-size:0.85rem;">{workflow_result.reflection_summary}</div>',
                unsafe_allow_html=True,
            )

        # ── Error ─────────────────────────────────────────────────────────────
        if workflow_result.error:
            st.error(f"Error: {workflow_result.error}")


def render_plan_timeline(plan: Plan) -> None:
    """
    Render just a plan's task timeline (without workflow metadata).
    Useful for the Workflow page.
    """
    _render_task_timeline(plan)


# ── Private ───────────────────────────────────────────────────────────────────

def _render_summary_bar(wr: WorkflowResult) -> None:
    """Render a one-line progress summary with metric chips."""
    if not wr.plan:
        return

    p = wr.plan.progress()
    cols = st.columns(5)
    cols[0].metric("Total",     p["total"])
    cols[1].metric("✅ Done",    p["completed"])
    cols[2].metric("❌ Failed",  p["failed"])
    cols[3].metric("⏭ Skipped", p["skipped"])
    cols[4].metric("⏱ Time",    f"{wr.total_time:.2f}s")
    st.markdown("")   # spacer


def _render_task_timeline(plan: Plan) -> None:
    """Render a vertical timeline of all tasks in the plan."""
    for task in plan.tasks:
        status_key = task.status.value if hasattr(task.status, "value") else str(task.status)
        icon, color = _TASK_ICON.get(status_key, ("?", "#8b949e"))

        tool_label = f" `{task.tool}`" if task.tool else ""

        # Task row
        col_icon, col_body = st.columns([1, 11])
        col_icon.markdown(
            f'<div style="font-size:1.1rem;padding-top:4px;">{icon}</div>',
            unsafe_allow_html=True,
        )
        col_body.markdown(
            f'<div style="border-left:2px solid {color};padding-left:10px;'
            f'margin-bottom:6px;">'
            f'<strong>[{task.id}] {task.description}</strong>'
            f'<span style="color:#8b949e;font-size:0.8rem;">{tool_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Output (collapsed by default unless failed)
        if task.output_text or task.error:
            with st.expander(
                "Output" if task.output_text else "Error",
                expanded=(status_key == "failed"),
            ):
                if task.error:
                    st.error(task.error)
                elif task.output_text:
                    st.code(task.output_text[:1000], language="text")
