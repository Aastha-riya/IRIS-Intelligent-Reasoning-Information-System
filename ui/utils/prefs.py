"""
ui/utils/prefs.py

User preferences — persistent settings backed by ui/config/settings.json.

Preferences are loaded from disk on first access in each session and
written back to disk whenever set_pref() or save_prefs() is called.
This means settings survive browser restarts.

Usage:
    from ui.utils.prefs import get_pref, set_pref, save_prefs, load_prefs

    model = get_pref("model")
    set_pref("temperature", 0.9)   # updates session + saves to disk
    save_prefs()                   # explicit flush to disk
"""

from __future__ import annotations

import streamlit as st
import config.settings as cfg


# ── Default values ────────────────────────────────────────────────────────────

_DEFAULTS: dict = {
    # Model
    "model":          cfg.DEFAULT_MODEL,
    "temperature":    cfg.LLM_TEMPERATURE,
    "max_tokens":     cfg.MAX_TOKENS,

    # Memory
    "max_history":           cfg.MAX_HISTORY,
    "max_context_history":   cfg.MAX_CONTEXT_HISTORY,
    "max_context_memories":  cfg.MAX_CONTEXT_MEMORIES,

    # Agent toggles
    "reflection_enabled": True,
    "planner_enabled":    True,
    "workflow_enabled":   True,
    "auto_memory":        True,

    # Voice
    "voice_enabled":  True,
    "auto_speak":     False,
    "voice_speed":    cfg.VOICE_SPEED,
    "voice_volume":   1.0,

    # Appearance
    "theme":               "dark",      # "dark" | "light" | "system"
    "accent_color":        "#1f6feb",
    "font_size":           "medium",    # "small" | "medium" | "large"
    "compact_mode":        False,
    "stream_responses":    True,
    "show_workflow_panel": True,
    "show_timestamps":     True,

    # Disabled tools (stored as list for JSON, used as set in memory)
    "disabled_tools": [],
}


# ── Session + disk sync ───────────────────────────────────────────────────────

def _prefs() -> dict:
    """Return in-session prefs dict, loading from disk on first access."""
    if "prefs" not in st.session_state:
        st.session_state["prefs"] = load_prefs()
    return st.session_state["prefs"]


def load_prefs() -> dict:
    """Load from disk, merging with defaults for any missing keys."""
    try:
        from ui.config.settings_io import load_settings
        stored = load_settings()
        # disabled_tools comes from disk as list, keep as list internally
        return stored
    except Exception:
        return dict(_DEFAULTS)


def save_prefs() -> None:
    """Flush current in-session prefs to settings.json."""
    try:
        from ui.config.settings_io import save_settings
        save_settings(_prefs())
    except Exception:
        pass


def reset_prefs() -> None:
    """Reset to defaults in session and on disk."""
    try:
        from ui.config.settings_io import reset_settings
        reset_settings()
    except Exception:
        pass
    st.session_state["prefs"] = dict(_DEFAULTS)


# ── Public read / write ───────────────────────────────────────────────────────

def get_pref(key: str):
    """Return the current value of a preference."""
    return _prefs().get(key, _DEFAULTS.get(key))


def set_pref(key: str, value) -> None:
    """Set a preference value and save to disk."""
    _prefs()[key] = value
    save_prefs()


def get_all_prefs() -> dict:
    """Return a copy of all current preferences."""
    return dict(_prefs())


# ── Tool helpers ──────────────────────────────────────────────────────────────

def is_tool_enabled(tool_name: str) -> bool:
    """Return True if the given tool is not in the disabled list."""
    disabled = get_pref("disabled_tools") or []
    return tool_name not in disabled


def toggle_tool(tool_name: str) -> None:
    """Enable a disabled tool or disable an enabled one."""
    disabled = list(get_pref("disabled_tools") or [])
    if tool_name in disabled:
        disabled.remove(tool_name)
    else:
        disabled.append(tool_name)
    set_pref("disabled_tools", disabled)
