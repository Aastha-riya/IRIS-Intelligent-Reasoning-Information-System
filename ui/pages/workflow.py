"""
ui/pages/workflow.py

Workflow page — manually trigger a multi-step workflow and watch it run.
"""

import streamlit as st

from ui.components.header import render_header
from ui.components.status import error as show_error, success as show_success
from ui.utils.session     import get_container


def render() -> None:
    render_header("Workflow", "Plan → Execute → Reflect")

    try:
        container = get_container()
        workflow  = container.workflow
    except Exception as exc:
        show_error(f"Workflow engine unavailable: {exc}")
        return

    st.markdown(
        "Run a multi-step goal through the full IRIS pipeline: "
        "Planner → Executor → Reflection Engine."
    )
    st.divider()

    goal = st.text_area(
        "Goal",
        placeholder="e.g. Analyse the project structure and generate a README",
        height=100,
        key="workflow_goal",
    )

    if st.button("▶ Run Workflow", key="run_workflow"):
        if not goal.strip():
            show_error("Please enter a goal.")
            return

        with st.spinner("🔄 Running workflow..."):
            try:
                result = workflow.run(goal.strip())
            except Exception as exc:
                show_error(f"Workflow error: {exc}")
                return

        # ── Result ────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Result")

        if result.succeeded():
            show_success(f"Completed in {result.total_time:.2f}s — {result.cycles} cycle(s)")
        else:
            show_error(f"Failed: {result.error or 'Unknown error'}")

        # Plan breakdown
        if result.plan:
            st.subheader("📋 Task Breakdown")
            for task in result.plan.tasks:
                icon = {
                    "completed": "✅",
                    "failed":    "❌",
                    "skipped":   "⏭️",
                    "cancelled": "🚫",
                }.get(task.status.value, "⏳")
                col1, col2, col3 = st.columns([1, 6, 3])
                col1.markdown(icon)
                col2.markdown(f"**[{task.id}]** {task.description}")
                tool_label = f"`{task.tool}`" if task.tool else "_no tool_"
                col3.markdown(tool_label)

                if task.output_text:
                    with st.expander("Output"):
                        st.markdown(task.output_text)

        # Reflection summary
        if result.reflection_summary:
            st.divider()
            st.subheader("🔍 Reflection")
            st.markdown(result.reflection_summary)
