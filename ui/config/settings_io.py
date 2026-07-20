"""
ui/config/settings_io.py

Persistent settings file I/O — saves to and loads from ui/config/settings.json.

This makes preferences survive browser restarts (unlike session_state which
resets every time). The file is written as plain JSON so it's human-editable.

Usage:
    from ui.config.settings_io import save_settings, load_settings, reset_settings

    prefs = load_settings()
    save_settings(prefs)
    reset_settings()
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ui.config.defaults import DEFAULTS

# ── Settings file path ────────────────────────────────────────────────────────

_SETTINGS_FILE = Path(__file__).parent / "settings.json"


# ── Public API ────────────────────────────────────────────────────────────────

def load_settings() -> dict:
    """
    Load settings from settings.json.
    Returns defaults for any key that is missing in the file.
    Creates settings.json with defaults if it doesn't exist.
    """
    if not _SETTINGS_FILE.exists():
        save_settings(DEFAULTS)
        return dict(DEFAULTS)

    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)

        # Merge: fill in any new keys added since last save
        result = dict(DEFAULTS)
        result.update(stored)
        return result

    except Exception:
        # Corrupted file — reset to defaults
        save_settings(DEFAULTS)
        return dict(DEFAULTS)


def save_settings(prefs: dict) -> None:
    """
    Write preferences to settings.json.
    Converts non-serialisable types (sets → lists) automatically.
    """
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Make a JSON-safe copy
    safe: dict = {}
    for k, v in prefs.items():
        if isinstance(v, set):
            safe[k] = list(v)
        else:
            safe[k] = v

    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=4, ensure_ascii=False)


def reset_settings() -> dict:
    """Overwrite settings.json with defaults and return the defaults dict."""
    save_settings(DEFAULTS)
    return dict(DEFAULTS)


def export_config() -> str:
    """Return the settings file contents as a JSON string for download."""
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return json.dumps(DEFAULTS, indent=4)


def import_config(json_str: str) -> dict:
    """
    Parse and validate an imported config JSON string.
    Unknown keys are ignored. Missing keys fall back to defaults.
    Returns the merged preferences dict.
    """
    try:
        imported = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    merged = dict(DEFAULTS)
    for k in DEFAULTS:
        if k in imported:
            merged[k] = imported[k]

    save_settings(merged)
    return merged
