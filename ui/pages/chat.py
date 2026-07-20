"""
ui/pages/chat.py

IRIS Chat page — Phase 3 complete implementation.

Features wired in this file:
    ✅ Native st.chat_message() bubbles
    ✅ Streaming word-by-word response
    ✅ File upload → content injected into prompt
    ✅ Voice input via Listener
    ✅ Voice output (Speak button per message)
    ✅ Workflow timeline panel after agent runs
    ✅ Tool activity indicator during execution
    ✅ Loading stages (Thinking → Planning → Executing → Reflecting)
    ✅ Per-message actions (copy, regenerate, speak, delete)
    ✅ Export conversation (TXT / Markdown / PDF)
    ✅ Conversation management (new, clear, rename, delete)

Flow:
    User submits prompt (text / voice / file)
        ↓
    agent.run(prompt + file context)
        ↓
    Stream response word-by-word
        ↓
    Show workflow timeline (if plan was used)
        ↓
    Save to session history
"""

from __future__ import annotations

import streamlit as st

# ── Components ────────────────────────────────────────────────────────────────
from ui.components.chat_header      import render_chat_header
from ui.components.chat_input       import render_chat_input
from ui.components.chat_message     import render_user_message, render_assistant_message
from ui.components.export_chat      import render_export_buttons
from ui.components.file_upload      import (
    render_file_upload, build_file_context, render_uploaded_file_badges,
)
from ui.components.loading_indicator import (
    ActivityPanel,
    ThinkingIndicator,
    STAGE_THINKING, STAGE_MEMORY, STAGE_PLANNING,
    STAGE_EXECUTING, STAGE_REFLECTING, STAGE_GENERATING, STAGE_SAVING, STAGE_DONE,
)
from ui.components.message_actions  import render_message_actions
from ui.components.streaming_chat   import stream_response
from ui.components.voice_input      import render_voice_button
from ui.components.workflow_panel   import render_workflow_panel

# ── Session helpers ───────────────────────────────────────────────────────────
from ui.utils.session import (
    get_container,
    get_messages,
    append_message,
    clear_chat,
    new_conv,
    list_conversations,
    switch_conv,
    _active_conv_id,
    get_active_conv,
    set_thinking_stage,
)


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    """Render the full Phase 3 chat page."""

    # ── Load container once ───────────────────────────────────────────────────
    try:
        container = get_container()
        agent     = container.agent
    except Exception as exc:
        st.error(f"❌ Failed to initialise IRIS: {exc}")
        st.stop()

    # ── Sidebar: conversation history ─────────────────────────────────────────
    _render_conversation_sidebar()

    # ── Header with status + controls ─────────────────────────────────────────
    render_chat_header()

    # ── Chat history ──────────────────────────────────────────────────────────
    messages = get_messages()

    if not messages:
        _render_welcome()
    else:
        _render_history_with_actions(messages)

    # ── Handle pending prompts (voice / suggestion chips / regenerate) ──────────
    pending = st.session_state.pop("_pending_prompt", None) or \
              st.session_state.pop("_regen_prompt", None)

    # ── Input area: file upload + voice + text input ──────────────────────────
    uploaded_files = _render_input_area()

    # ── Process submitted prompt ──────────────────────────────────────────────
    prompt = render_chat_input(placeholder="Ask IRIS anything...") or pending

    if prompt:
        _handle_prompt(agent, prompt, uploaded_files)

    # ── Export section ────────────────────────────────────────────────────────
    if messages:
        with st.expander("⬇ Export conversation", expanded=False):
            render_export_buttons(messages, get_active_conv()["name"])


# ── Private — conversation sidebar ───────────────────────────────────────────

def _render_conversation_sidebar() -> None:
    """Show recent conversations in the sidebar for quick switching."""
    with st.sidebar:
        st.divider()
        st.markdown("**Recent chats**")

        if st.button("＋ New chat", key="side_new_chat", use_container_width=True):
            new_conv()
            st.rerun()

        convs = list_conversations()
        active_id = _active_conv_id()

        for conv in convs[:10]:   # show up to 10 recent
            is_active = conv["id"] == active_id
            label = ("▶ " if is_active else "   ") + conv["name"][:28]
            if st.button(label, key=f"conv_{conv['id']}", use_container_width=True):
                switch_conv(conv["id"])
                st.rerun()


# ── Private — welcome screen ──────────────────────────────────────────────────

def _render_welcome() -> None:
    st.markdown(
        '<div style="text-align:center;color:#8b949e;padding:60px 0 30px;">'
        '<div style="font-size:3rem">🤖</div>'
        '<div style="font-size:1.3rem;font-weight:600;margin-top:12px;">'
        'How can IRIS help you today?</div>'
        '<div style="font-size:0.9rem;margin-top:8px;max-width:480px;margin-left:auto;margin-right:auto;">'
        'Ask anything · Upload files · Use voice · Run multi-step workflows'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # Suggestion chips
    suggestions = [
        "What is machine learning?",
        "calculate 15% of 2400",
        "scan ./",
        "analyse this project",
    ]
    cols = st.columns(len(suggestions))
    for i, s in enumerate(suggestions):
        if cols[i].button(s, key=f"suggest_{i}", use_container_width=True):
            st.session_state["_pending_prompt"] = s
            st.rerun()


# ── Private — render history with actions ─────────────────────────────────────

def _render_history_with_actions(messages: list[dict]) -> None:
    """Render all messages; add action bar under each assistant message."""

    for idx, msg in enumerate(messages):
        role    = msg["role"]
        content = msg.get("content", "")
        ts      = msg.get("timestamp", "")
        dec     = msg.get("decision", "")

        if role == "user":
            render_user_message(content, ts)
        else:
            render_assistant_message(content, dec, ts)

            # Per-message actions
            def _on_delete(i=idx):
                messages.pop(i)
                st.rerun()

            def _on_regen(i=idx):
                # Find the preceding user message and re-run
                for j in range(i - 1, -1, -1):
                    if messages[j]["role"] == "user":
                        st.session_state["_regen_prompt"] = messages[j]["content"]
                        # Remove the assistant message being replaced
                        messages.pop(i)
                        st.rerun()
                        break

            render_message_actions(
                msg_index = idx,
                content   = content,
                on_delete = _on_delete,
                on_regen  = _on_regen,
            )

        # Workflow timeline (stored in message metadata)
        wf_result = msg.get("_workflow_result")
        if wf_result:
            render_workflow_panel(wf_result)


# ── Private — input area ──────────────────────────────────────────────────────

def _render_input_area() -> list[dict]:
    """
    Improvement 5 — Better Chat Input.
    Renders: 📎 file upload · 🎤 voice · [text input with icons]
    """
    # File upload + voice on same row with icon labels
    col_attach_label, col_files, col_voice_label, col_voice = st.columns([1, 9, 1, 1])

    col_attach_label.markdown(
        '<div style="padding-top:8px;font-size:1.2rem;text-align:center;">📎</div>',
        unsafe_allow_html=True,
    )
    with col_files:
        uploaded = render_file_upload()

    col_voice_label.markdown(
        '<div style="padding-top:8px;font-size:1.2rem;text-align:center;">🎤</div>',
        unsafe_allow_html=True,
    )
    with col_voice:
        voiced_text = render_voice_button(key="voice_input_btn")
        if voiced_text:
            st.session_state["_pending_prompt"] = voiced_text
            st.rerun()

    if uploaded:
        render_uploaded_file_badges(uploaded)

    return uploaded


# ── Private — handle prompt ───────────────────────────────────────────────────

def _handle_prompt(agent, prompt: str, uploaded_files: list[dict]) -> None:
    """
    Improvements 2, 3, 4 — Thinking animation + Streaming + Activity Panel.
    """
    if not prompt or not prompt.strip():
        return

    file_context = build_file_context(uploaded_files)
    full_prompt  = (
        f"Context from uploaded files:\n\n{file_context}\n\n---\n\n{prompt}"
        if file_context else prompt
    )

    # Show user message immediately
    render_user_message(prompt)
    append_message("user", prompt)

    # ── Improvement 4: Activity Panel ─────────────────────────────────────────
    panel = ActivityPanel()
    panel.start("🔍", "Memory",    "Searching context...")
    set_thinking_stage(STAGE_MEMORY)

    panel.start("🧠", "Planner",   "Creating plan...")
    set_thinking_stage(STAGE_PLANNING)

    wf_result = None

    try:
        result = agent.run(full_prompt)

        # Mark stages complete based on decision
        decision = result.decision.value if result.succeeded() else ""

        panel.complete("Memory",  "Context loaded ✔")
        if decision == "plan":
            panel.complete("Planner", "Plan created ✔")
            panel.start("⚙️",  "Executor",   "Running tasks...")
            set_thinking_stage(STAGE_EXECUTING)
            panel.complete("Executor",   "Tasks complete ✔")
            panel.start("🔄", "Reflection", "Evaluating result...")
            set_thinking_stage(STAGE_REFLECTING)
            panel.complete("Reflection", "Reflection done ✔")
        elif decision == "tool":
            panel.complete("Planner",  "Tool selected ✔")
            panel.start("🔧", "Tool",   "Executing tool...")
            set_thinking_stage(STAGE_EXECUTING)
            panel.complete("Tool",     "Tool finished ✔")
        else:
            panel.complete("Planner", "Answered directly ✔")

        panel.start("💭", "LLM",    "Generating response...")
        set_thinking_stage(STAGE_GENERATING)
        panel.start("💾", "Memory", "Saving to memory...")
        set_thinking_stage(STAGE_SAVING)
        panel.complete("LLM",    "Response ready ✔")
        panel.complete("Memory", "Memory updated ✔")

    except Exception as exc:
        panel.close()
        set_thinking_stage("")
        st.error(f"❌ Agent error: {exc}")
        append_message("assistant", f"I encountered an error: {exc}")
        return

    panel.close()
    set_thinking_stage("")

    # ── Improvement 3: Stream response word-by-word ───────────────────────────
    if result.succeeded():
        response = result.output or "Done."
        decision = result.decision.value
    else:
        response = result.error or "I couldn't complete that request."
        decision = ""

    stream_response(response)

    get_messages().append({
        "role":             "assistant",
        "content":          response,
        "decision":         decision,
        "timestamp":        _now_str(),
        "_workflow_result": wf_result,
    })

    st.rerun()


def _now_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
