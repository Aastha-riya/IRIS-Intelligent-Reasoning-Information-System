"""
ui/components/voice_input.py

Voice input component for the IRIS Streamlit UI.

Wraps the existing voice/listen.py Listener class.
Runs recognition in a background thread so Streamlit doesn't freeze.

Flow:
    User clicks 🎤 → background thread starts → Listener.listen() → transcribed text
    → returned to chat page → submitted to agent

Note:
    Google Speech Recognition requires an internet connection.
    SpeechRecognition + pyaudio must be installed.
"""

from __future__ import annotations

import threading

import streamlit as st


def render_voice_button(key: str = "voice_btn") -> str | None:
    """
    Render the microphone button. When clicked, starts recording and
    returns the transcribed text, or None if recording fails / is cancelled.

    This is a blocking operation — it shows a spinner while listening.

    Returns:
        Transcribed text string, or None.
    """
    if not st.button("🎤", key=key, help="Click to speak"):
        return None

    result_holder: dict = {"text": None, "error": None}

    def _listen() -> None:
        try:
            from voice.listen import Listener
            listener = Listener()
            result_holder["text"] = listener.listen()
        except Exception as e:
            result_holder["error"] = str(e)

    with st.spinner("🎤 Listening — speak now..."):
        t = threading.Thread(target=_listen, daemon=True)
        t.start()
        t.join(timeout=15)   # max 15 seconds of listening

    if result_holder["error"]:
        st.error(f"Voice input failed: {result_holder['error']}")
        return None

    text = result_holder.get("text") or ""

    if not text:
        st.warning("Could not understand audio. Please try again.")
        return None

    st.success(f'🎤 Heard: "{text}"')
    return text
