"""
ui/components/status.py

Reusable status/info banners for the IRIS UI.
"""

import streamlit as st


def info(message: str) -> None:
    st.markdown(
        f'<div style="background:#1f6feb22;border:1px solid #1f6feb;'
        f'border-radius:8px;padding:10px 14px;color:#79c0ff;">'
        f'ℹ️ {message}</div>',
        unsafe_allow_html=True,
    )


def success(message: str) -> None:
    st.markdown(
        f'<div style="background:#2ea04322;border:1px solid #2ea043;'
        f'border-radius:8px;padding:10px 14px;color:#56d364;">'
        f'✅ {message}</div>',
        unsafe_allow_html=True,
    )


def warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#bb800922;border:1px solid #bb8009;'
        f'border-radius:8px;padding:10px 14px;color:#e3b341;">'
        f'⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def error(message: str) -> None:
    st.markdown(
        f'<div style="background:#f8514922;border:1px solid #f85149;'
        f'border-radius:8px;padding:10px 14px;color:#f85149;">'
        f'❌ {message}</div>',
        unsafe_allow_html=True,
    )
