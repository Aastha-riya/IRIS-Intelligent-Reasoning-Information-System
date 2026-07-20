"""
ui/components/header.py

Page header component — IRIS logo + title + agent status badge.
"""

import streamlit as st


def render_header(title: str = "IRIS", subtitle: str = "") -> None:
    """Render the top header with logo and optional subtitle."""
    col1, col2 = st.columns([1, 8])
    with col1:
        st.markdown("# 🤖")
    with col2:
        st.markdown(f"## {title}")
        if subtitle:
            st.markdown(
                f'<p style="color:#8b949e;margin-top:-10px;">{subtitle}</p>',
                unsafe_allow_html=True,
            )
    st.divider()
