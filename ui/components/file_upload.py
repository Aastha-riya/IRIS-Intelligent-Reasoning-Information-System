"""
ui/components/file_upload.py

File upload component for IRIS.

Supports: PDF, DOCX, TXT, CSV, XLSX, images (PNG/JPG), ZIP
Flow:
    Upload File → Extract Text → Append to User Prompt → Agent Analyses It

The extracted text is prepended to the user's prompt so the agent
can analyse it without any changes to agent code.
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path

import streamlit as st


# ── Supported types ───────────────────────────────────────────────────────────

ACCEPTED_TYPES = [
    "text/plain",
    "text/csv",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/zip",
]

ACCEPTED_EXTENSIONS = [
    ".txt", ".csv", ".pdf", ".docx", ".xlsx",
    ".png", ".jpg", ".jpeg", ".zip",
]

MAX_FILE_SIZE_MB = 10


# ── Public API ────────────────────────────────────────────────────────────────

def render_file_upload() -> list[dict]:
    """
    Render the file upload widget.

    Returns:
        List of dicts: [{"name": str, "type": str, "text": str, "size": int}]
        Each dict represents one uploaded file with its extracted text.
        Returns [] if no files are uploaded.
    """
    uploaded = st.file_uploader(
        "📎 Attach files",
        type=[e.lstrip(".") for e in ACCEPTED_EXTENSIONS],
        accept_multiple_files=True,
        key="file_uploader",
        label_visibility="collapsed",
        help=f"Supported: PDF, DOCX, TXT, CSV, XLSX, images, ZIP. Max {MAX_FILE_SIZE_MB} MB each.",
    )

    if not uploaded:
        return []

    results: list[dict] = []

    for f in uploaded:
        size_mb = len(f.getbuffer()) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            st.warning(f"⚠️ `{f.name}` exceeds {MAX_FILE_SIZE_MB} MB — skipped.")
            continue

        text = _extract_text(f)
        results.append({
            "name": f.name,
            "type": f.type or "unknown",
            "text": text,
            "size": len(f.getbuffer()),
        })

    return results


def build_file_context(files: list[dict]) -> str:
    """
    Build a context block from uploaded files to prepend to the user prompt.

    Example output:
        [File: report.pdf]
        Lorem ipsum...

        [File: data.csv]
        col1,col2\n1,2\n...
    """
    if not files:
        return ""

    blocks = []
    for f in files:
        excerpt = f["text"][:3000]   # cap per file to stay within context budget
        if len(f["text"]) > 3000:
            excerpt += "\n... [truncated]"
        blocks.append(f"[File: {f['name']}]\n{excerpt}")

    return "\n\n".join(blocks)


def render_uploaded_file_badges(files: list[dict]) -> None:
    """Show small pill badges for each uploaded file with a size label."""
    if not files:
        return
    cols = st.columns(min(len(files), 4))
    for i, f in enumerate(files):
        size_kb = f["size"] // 1024
        cols[i % 4].markdown(
            f'<span style="background:#21262d;border:1px solid #30363d;'
            f'border-radius:8px;padding:3px 10px;font-size:0.78rem;'
            f'color:#8b949e;">📄 {f["name"]} ({size_kb} KB)</span>',
            unsafe_allow_html=True,
        )


# ── Private — text extractors ─────────────────────────────────────────────────

def _extract_text(file) -> str:
    """Dispatch to the correct extractor based on file extension."""
    name = file.name.lower()
    ext  = Path(name).suffix

    try:
        if ext == ".txt" or ext == ".csv":
            return file.read().decode("utf-8", errors="replace")

        elif ext == ".pdf":
            return _extract_pdf(file)

        elif ext == ".docx":
            return _extract_docx(file)

        elif ext == ".xlsx":
            return _extract_xlsx(file)

        elif ext in (".png", ".jpg", ".jpeg"):
            return f"[Image file: {file.name} — image content cannot be extracted as text]"

        elif ext == ".zip":
            return _extract_zip(file)

        else:
            return file.read().decode("utf-8", errors="replace")

    except Exception as e:
        return f"[Could not read {file.name}: {e}]"


def _extract_pdf(file) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        pages  = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages)
    except ImportError:
        return "[PDF extraction requires: pip install PyPDF2]"


def _extract_docx(file) -> str:
    try:
        import docx
        doc  = docx.Document(io.BytesIO(file.read()))
        text = "\n".join(p.text for p in doc.paragraphs)
        return text
    except ImportError:
        return "[DOCX extraction requires: pip install python-docx]"


def _extract_xlsx(file) -> str:
    try:
        import openpyxl
        wb   = openpyxl.load_workbook(io.BytesIO(file.read()), data_only=True)
        rows = []
        for sheet in wb.worksheets:
            rows.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                rows.append(",".join(str(c) if c is not None else "" for c in row))
        return "\n".join(rows)
    except ImportError:
        return "[XLSX extraction requires: pip install openpyxl]"


def _extract_zip(file) -> str:
    lines = []
    try:
        with zipfile.ZipFile(io.BytesIO(file.read())) as zf:
            for name in zf.namelist()[:20]:   # cap at 20 files
                lines.append(f"  {name}")
        return f"ZIP contents ({len(lines)} files shown):\n" + "\n".join(lines)
    except Exception as e:
        return f"[ZIP read error: {e}]"
