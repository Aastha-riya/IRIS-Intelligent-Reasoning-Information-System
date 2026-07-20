"""
ui/components/export_chat.py

Export conversation history to TXT, Markdown, or PDF.

TXT and Markdown are generated in-memory — no extra dependencies.
PDF uses fpdf2 — falls back to Markdown if not installed.

Usage:
    render_export_buttons(messages)
"""

from __future__ import annotations

import io
from datetime import datetime

import streamlit as st


# ── Public API ────────────────────────────────────────────────────────────────

def render_export_buttons(
    messages:       list[dict],
    conv_name:      str = "IRIS Chat",
) -> None:
    """
    Render TXT, Markdown and PDF download buttons for the conversation.

    Args:
        messages:  List of message dicts {role, content, timestamp}.
        conv_name: Conversation name used in the filename and header.
    """
    if not messages:
        st.caption("No messages to export.")
        return

    st.markdown("**Export conversation**")
    col_txt, col_md, col_pdf = st.columns(3)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = conv_name.replace(" ", "_")

    # ── TXT ───────────────────────────────────────────────────────────────────
    with col_txt:
        txt_bytes = _build_txt(messages, conv_name)
        st.download_button(
            label     = "⬇ TXT",
            data      = txt_bytes,
            file_name = f"{safe_name}_{timestamp}.txt",
            mime      = "text/plain",
            key       = "export_txt",
            use_container_width = True,
        )

    # ── Markdown ──────────────────────────────────────────────────────────────
    with col_md:
        md_bytes = _build_markdown(messages, conv_name)
        st.download_button(
            label     = "⬇ Markdown",
            data      = md_bytes,
            file_name = f"{safe_name}_{timestamp}.md",
            mime      = "text/markdown",
            key       = "export_md",
            use_container_width = True,
        )

    # ── PDF ───────────────────────────────────────────────────────────────────
    with col_pdf:
        pdf_bytes = _build_pdf(messages, conv_name)
        if pdf_bytes:
            st.download_button(
                label     = "⬇ PDF",
                data      = pdf_bytes,
                file_name = f"{safe_name}_{timestamp}.pdf",
                mime      = "application/pdf",
                key       = "export_pdf",
                use_container_width = True,
            )
        else:
            st.button(
                "⬇ PDF",
                disabled    = True,
                help        = "Install fpdf2 to enable PDF export: pip install fpdf2",
                key         = "export_pdf_disabled",
                use_container_width = True,
            )


# ── Private — format builders ─────────────────────────────────────────────────

def _build_txt(messages: list[dict], title: str) -> bytes:
    """Build a plain text export."""
    lines = [
        f"IRIS Conversation Export",
        f"Title:   {title}",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Messages: {len(messages)}",
        "=" * 60,
        "",
    ]

    for msg in messages:
        role      = "You" if msg["role"] == "user" else "IRIS"
        ts        = msg.get("timestamp", "")
        content   = msg.get("content", "")
        ts_label  = f" [{ts}]" if ts else ""

        lines.append(f"{role}{ts_label}:")
        lines.append(content)
        lines.append("")

    return "\n".join(lines).encode("utf-8")


def _build_markdown(messages: list[dict], title: str) -> bytes:
    """Build a Markdown export."""
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# {title}",
        f"",
        f"> Exported: {now} · {len(messages)} messages",
        f"",
        "---",
        "",
    ]

    for msg in messages:
        role    = msg["role"]
        content = msg.get("content", "")
        ts      = msg.get("timestamp", "")
        ts_md   = f" *{ts}*" if ts else ""

        if role == "user":
            lines.append(f"### 🧑 You{ts_md}")
        else:
            decision  = msg.get("decision", "")
            badge     = f" `[{decision}]`" if decision else ""
            lines.append(f"### 🤖 IRIS{badge}{ts_md}")

        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).encode("utf-8")


def _build_pdf(messages: list[dict], title: str) -> bytes | None:
    """
    Build a PDF export using fpdf2.
    Returns None if fpdf2 is not installed.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        return None

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Header ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(
        0, 6,
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
        f"{len(messages)} messages",
        ln=True,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Messages ──────────────────────────────────────────────────────────────
    for msg in messages:
        role    = msg["role"]
        content = msg.get("content", "")
        ts      = msg.get("timestamp", "")

        # Speaker label
        pdf.set_font("Helvetica", "B", 10)
        label = ("You" if role == "user" else "IRIS") + (f"  [{ts}]" if ts else "")
        if role == "user":
            pdf.set_text_color(31, 111, 235)
        else:
            pdf.set_text_color(86, 211, 100)
        pdf.cell(0, 6, label, ln=True)
        pdf.set_text_color(0, 0, 0)

        # Content — fpdf multi_cell handles line wrapping
        pdf.set_font("Helvetica", "", 9)
        safe_content = content.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 5, safe_content)
        pdf.ln(3)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
