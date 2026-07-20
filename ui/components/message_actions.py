"""
ui/components/message_actions.py

Per-message action buttons for assistant messages.

Actions:
    📋 Copy     — copy text to clipboard via JavaScript
    🔄 Regenerate — re-run the last prompt through the agent
    🔊 Speak    — speak the message using the existing Speaker
    🗑 Delete   — remove the message from history
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


# ── Public API ────────────────────────────────────────────────────────────────

def render_message_actions(
    msg_index:  int,
    content:    str,
    on_delete:  callable | None = None,
    on_regen:   callable | None = None,
) -> None:
    """
    Render a compact action bar below an assistant message.

    Args:
        msg_index: Position in the message list (used for unique widget keys).
        content:   The message text (for copy and speak).
        on_delete: Callback called when the user confirms deletion.
        on_regen:  Callback called when the user clicks Regenerate.
    """
    col_copy, col_regen, col_speak, col_delete, col_spacer = st.columns(
        [1, 1, 1, 1, 8]
    )

    # ── Copy ──────────────────────────────────────────────────────────────────
    with col_copy:
        if st.button("📋", key=f"copy_{msg_index}", help="Copy to clipboard"):
            _copy_to_clipboard(content)
            st.toast("Copied!", icon="✅")

    # ── Regenerate ────────────────────────────────────────────────────────────
    with col_regen:
        if st.button("🔄", key=f"regen_{msg_index}", help="Regenerate response"):
            if on_regen:
                on_regen()

    # ── Speak ─────────────────────────────────────────────────────────────────
    with col_speak:
        if st.button("🔊", key=f"speak_{msg_index}", help="Speak this message"):
            _speak_text(content)

    # ── Delete ────────────────────────────────────────────────────────────────
    with col_delete:
        if st.button("🗑", key=f"del_msg_{msg_index}", help="Delete this message"):
            st.session_state[f"confirm_del_msg_{msg_index}"] = True

    # ── Delete confirmation ───────────────────────────────────────────────────
    if st.session_state.get(f"confirm_del_msg_{msg_index}"):
        col_yes, col_no, _ = st.columns([1, 1, 8])
        if col_yes.button("Delete", key=f"del_yes_{msg_index}"):
            st.session_state.pop(f"confirm_del_msg_{msg_index}", None)
            if on_delete:
                on_delete()
        if col_no.button("Keep", key=f"del_no_{msg_index}"):
            st.session_state.pop(f"confirm_del_msg_{msg_index}", None)


# ── Private helpers ───────────────────────────────────────────────────────────

def _copy_to_clipboard(text: str) -> None:
    """Inject JavaScript to copy text to the clipboard."""
    escaped = text.replace("`", "\\`").replace("\\", "\\\\")
    components.html(
        f"""
        <script>
        navigator.clipboard.writeText(`{escaped}`)
          .catch(function() {{
            var el = document.createElement('textarea');
            el.value = `{escaped}`;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
          }});
        </script>
        """,
        height=0,
    )


def _speak_text(text: str) -> None:
    """Speak the message using the IRIS Speaker in a background thread."""
    import threading
    def _run():
        try:
            from voice.speak import Speaker
            speaker = Speaker()
            speaker.speak(text[:500])   # cap to avoid very long TTS
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
