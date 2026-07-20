"""
ui/utils/session.py

Session state management for the IRIS Streamlit UI.

The Container (with all models) is built exactly once and stored in
st.session_state["iris_container"]. Every Streamlit rerun reuses the
same objects — no re-loading models on every keystroke.

Conversation model:
    Each conversation is a dict:
    {
        "id":       str (uuid),
        "name":     str,
        "messages": list[{role, content, decision, timestamp}],
        "created":  str (ISO timestamp),
    }

All conversations live in st.session_state["conversations"].
The active conversation ID is st.session_state["active_conv_id"].
"""

from __future__ import annotations

import uuid
from datetime import datetime

import streamlit as st


# ── Container ─────────────────────────────────────────────────────────────────

def get_container():
    """
    Return the IRIS Container, building it once per browser session.
    Cached in st.session_state["iris_container"].
    """
    if "iris_container" not in st.session_state:
        from app.startup import Startup
        with st.spinner("🔧 Initialising IRIS — loading models..."):
            st.session_state["iris_container"] = Startup.initialize()
    return st.session_state["iris_container"]


# ── Agent status ──────────────────────────────────────────────────────────────

def get_agent_status() -> str:
    """Return the current agent status string ('idle', 'running', etc.)."""
    try:
        return get_container().agent.status.value
    except Exception:
        return "offline"


def get_thinking_stage() -> str:
    """Return the current thinking stage label (set during agent execution)."""
    return st.session_state.get("thinking_stage", "")


def set_thinking_stage(stage: str) -> None:
    st.session_state["thinking_stage"] = stage


# ── Conversation management ───────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _all_conversations() -> dict[str, dict]:
    """Return the full conversations dict, initialising if absent."""
    if "conversations" not in st.session_state:
        st.session_state["conversations"] = {}
    return st.session_state["conversations"]


def _active_conv_id() -> str:
    """Return the active conversation ID, creating one if none exists."""
    convs = _all_conversations()
    if "active_conv_id" not in st.session_state or \
       st.session_state["active_conv_id"] not in convs:
        new_conv()
    return st.session_state["active_conv_id"]


def new_conv(name: str = "") -> str:
    """
    Create a new empty conversation and make it active.
    Returns the new conversation ID.
    """
    conv_id = str(uuid.uuid4())
    convs   = _all_conversations()
    count   = len(convs) + 1
    convs[conv_id] = {
        "id":       conv_id,
        "name":     name or f"Chat {count}",
        "messages": [],
        "created":  _now(),
    }
    st.session_state["active_conv_id"] = conv_id
    return conv_id


def get_active_conv() -> dict:
    """Return the active conversation dict."""
    return _all_conversations()[_active_conv_id()]


def get_messages() -> list[dict]:
    """Return the message list for the active conversation."""
    return get_active_conv()["messages"]


def append_message(
    role:     str,
    content:  str,
    decision: str = "",
) -> None:
    """Append a message to the active conversation."""
    get_messages().append({
        "role":      role,
        "content":   content,
        "decision":  decision,
        "timestamp": _now(),
    })


def clear_chat() -> None:
    """Clear messages from the active conversation (keeps the conversation)."""
    get_active_conv()["messages"] = []


def delete_conv(conv_id: str) -> None:
    """Delete a conversation. If it was active, switch to a new one."""
    convs = _all_conversations()
    convs.pop(conv_id, None)
    if st.session_state.get("active_conv_id") == conv_id:
        if convs:
            st.session_state["active_conv_id"] = next(iter(convs))
        else:
            new_conv()


def rename_conv(conv_id: str, new_name: str) -> None:
    """Rename a conversation."""
    convs = _all_conversations()
    if conv_id in convs:
        convs[conv_id]["name"] = new_name.strip() or convs[conv_id]["name"]


def switch_conv(conv_id: str) -> None:
    """Switch to an existing conversation."""
    if conv_id in _all_conversations():
        st.session_state["active_conv_id"] = conv_id


def list_conversations() -> list[dict]:
    """
    Return all conversations sorted by:
    1. Pinned conversations first
    2. Then by creation time, newest first.
    """
    return sorted(
        _all_conversations().values(),
        key=lambda c: (not c.get("pinned", False), c["created"]),
        reverse=False,
    )


def pin_conv(conv_id: str) -> None:
    """Toggle the pinned status of a conversation."""
    convs = _all_conversations()
    if conv_id in convs:
        convs[conv_id]["pinned"] = not convs[conv_id].get("pinned", False)


def search_conversations(query: str) -> list[dict]:
    """
    Return conversations whose name or message content contains the query.
    Case-insensitive.
    """
    q = query.lower().strip()
    if not q:
        return list_conversations()

    results = []
    for conv in _all_conversations().values():
        # Match on conversation name
        if q in conv["name"].lower():
            results.append(conv)
            continue
        # Match on any message content
        if any(q in m.get("content", "").lower() for m in conv["messages"]):
            results.append(conv)

    return sorted(results, key=lambda c: c["created"], reverse=True)


# ── Legacy helpers (Phase 1 compatibility) ───────────────────────────────────

def get_chat_history() -> list[dict]:
    """Alias for get_messages() — kept for backward compatibility."""
    return get_messages()


# ── Page / theme state ────────────────────────────────────────────────────────

def get_active_page() -> str:
    return st.session_state.get("active_page", "Chat")


def set_active_page(page: str) -> None:
    st.session_state["active_page"] = page


def get_theme() -> str:
    return st.session_state.get("theme", "dark")


def toggle_theme() -> None:
    current = get_theme()
    st.session_state["theme"] = "light" if current == "dark" else "dark"
