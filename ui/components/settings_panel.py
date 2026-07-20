"""
ui/components/settings_panel.py

Appearance settings panel — Step 8.
Dark / Light / System theme, accent colour, font size, compact mode.
Injects dynamic CSS when settings change.
"""

from __future__ import annotations

import streamlit as st

from ui.utils.prefs import get_pref, set_pref


# ── CSS templates ─────────────────────────────────────────────────────────────

_FONT_SIZES = {
    "small":  "13px",
    "medium": "15px",
    "large":  "17px",
}

_COMPACT_CSS = """
<style>
[data-testid="stChatMessage"] { padding: 4px 8px !important; }
.element-container { margin-bottom: 4px !important; }
</style>
"""


def inject_appearance_css() -> None:
    """
    Inject CSS based on current appearance preferences.
    Call once near the top of app.py after inject_css().
    """
    accent  = get_pref("accent_color") or "#1f6feb"
    fs      = _FONT_SIZES.get(get_pref("font_size") or "medium", "15px")
    compact = get_pref("compact_mode") or False

    dynamic_css = f"""
    <style>
    html, body, [data-testid="stAppViewContainer"] {{
        font-size: {fs} !important;
    }}
    .stButton > button {{
        background: linear-gradient(135deg, {accent}, {accent}cc) !important;
    }}
    a {{ color: {accent} !important; }}
    </style>
    """
    st.markdown(dynamic_css, unsafe_allow_html=True)
    if compact:
        st.markdown(_COMPACT_CSS, unsafe_allow_html=True)


# ── Public render ─────────────────────────────────────────────────────────────

def render_appearance_settings() -> None:
    """Render the appearance settings section (Step 8)."""
    st.markdown("### 🎨 Appearance")

    col1, col2 = st.columns(2)

    # ── Theme ─────────────────────────────────────────────────────────────────
    with col1:
        theme = st.selectbox(
            "Theme",
            ["dark", "light", "system"],
            index={"dark": 0, "light": 1, "system": 2}.get(
                get_pref("theme") or "dark", 0
            ),
            help=(
                "dark = always dark  |  light = always light  |  "
                "system = follow OS preference (requires reload)"
            ),
        )
        set_pref("theme", theme)

        font_size = st.selectbox(
            "Font size",
            ["small", "medium", "large"],
            index={"small": 0, "medium": 1, "large": 2}.get(
                get_pref("font_size") or "medium", 1
            ),
        )
        set_pref("font_size", font_size)

    # ── Accent colour + compact ───────────────────────────────────────────────
    with col2:
        accent = st.color_picker(
            "Accent colour",
            value=get_pref("accent_color") or "#1f6feb",
            help="Used for buttons, links, and active states.",
        )
        set_pref("accent_color", accent)

        compact = st.toggle(
            "Compact mode",
            value=bool(get_pref("compact_mode")),
            help="Reduce spacing between elements for a denser layout.",
        )
        set_pref("compact_mode", compact)

    st.caption(
        "Font size and compact mode take effect immediately. "
        "Theme changes may require a page reload."
    )

    # ── Live preview ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Preview**")
    st.markdown(
        f'<div style="background:#21262d;border:1px solid #30363d;'
        f'border-radius:10px;padding:14px 18px;font-size:{_FONT_SIZES.get(font_size, "15px")};">'
        f'<span style="color:{accent};font-weight:600;">IRIS</span> — '
        f'How can I help you today?'
        f'</div>',
        unsafe_allow_html=True,
    )
