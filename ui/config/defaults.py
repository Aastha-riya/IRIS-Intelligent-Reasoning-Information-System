"""
ui/config/defaults.py

Default values for all user-configurable settings.
These are loaded when settings.json does not exist or is reset.

Keep in sync with ui/utils/prefs.py _DEFAULTS dict.
"""

import config.settings as cfg

DEFAULTS: dict = {
    # ── Identity ──────────────────────────────────────────────────────────────
    "assistant_name": cfg.ASSISTANT_NAME,

    # ── Model ─────────────────────────────────────────────────────────────────
    "model":          cfg.DEFAULT_MODEL,
    "temperature":    cfg.LLM_TEMPERATURE,
    "max_tokens":     cfg.MAX_TOKENS,

    # ── Memory ────────────────────────────────────────────────────────────────
    "max_history":           cfg.MAX_HISTORY,
    "max_context_history":   cfg.MAX_CONTEXT_HISTORY,
    "max_context_memories":  cfg.MAX_CONTEXT_MEMORIES,

    # ── Agent toggles ─────────────────────────────────────────────────────────
    "reflection_enabled": True,
    "planner_enabled":    True,
    "workflow_enabled":   True,
    "auto_memory":        True,

    # ── Voice ─────────────────────────────────────────────────────────────────
    "voice_enabled":  True,
    "auto_speak":     False,
    "voice_speed":    cfg.VOICE_SPEED,
    "voice_volume":   1.0,

    # ── Appearance ────────────────────────────────────────────────────────────
    "theme":              "dark",       # "dark" | "light" | "system"
    "accent_color":       "#1f6feb",    # hex
    "font_size":          "medium",     # "small" | "medium" | "large"
    "compact_mode":       False,
    "stream_responses":   True,
    "show_workflow_panel": True,
    "show_timestamps":    True,

    # ── Disabled tools ────────────────────────────────────────────────────────
    "disabled_tools": [],   # JSON-serialisable list (not a set)
}
