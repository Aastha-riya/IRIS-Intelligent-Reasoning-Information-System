"""
ui/components/diagnostics.py

Diagnostics panel — Step 10.
Runs health checks against every IRIS subsystem and reports pass/fail.

Checks:
    ✅ Check Ollama     — ping the model with a minimal prompt
    ✅ Test Memory      — save and retrieve a test entry
    ✅ Test Tools       — run each enabled tool with a safe query
    ✅ Test Voice       — initialise the TTS engine
    ✅ Run Health Check — all of the above in sequence
"""

from __future__ import annotations

import streamlit as st


# ── Result helpers ────────────────────────────────────────────────────────────

def _ok(label: str, detail: str = "") -> None:
    st.markdown(
        f'<div style="background:#2ea04322;border:1px solid #2ea043;'
        f'border-radius:8px;padding:8px 14px;margin:4px 0;font-size:0.88rem;">'
        f'✅ <strong>{label}</strong>'
        f'{"<br><span style=color:#8b949e;>" + detail + "</span>" if detail else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _fail(label: str, detail: str = "") -> None:
    st.markdown(
        f'<div style="background:#f8514922;border:1px solid #f85149;'
        f'border-radius:8px;padding:8px 14px;margin:4px 0;font-size:0.88rem;">'
        f'❌ <strong>{label}</strong>'
        f'{"<br><span style=color:#f85149;>" + detail[:120] + "</span>" if detail else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _warn(label: str, detail: str = "") -> None:
    st.markdown(
        f'<div style="background:#bb800922;border:1px solid #bb8009;'
        f'border-radius:8px;padding:8px 14px;margin:4px 0;font-size:0.88rem;">'
        f'⚠️ <strong>{label}</strong>'
        f'{"<br><span style=color:#e3b341;>" + detail + "</span>" if detail else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Individual checks ─────────────────────────────────────────────────────────

def check_ollama(model: str) -> tuple[bool, str]:
    try:
        import ollama
        resp = ollama.chat(
            model    = model,
            messages = [{"role": "user", "content": "Reply with: OK"}],
        )
        reply = resp["message"]["content"].strip()[:60]
        return True, f"Model responded: {reply}"
    except Exception as e:
        return False, str(e)


def check_memory(container) -> tuple[bool, str]:
    try:
        mm = container.memory_manager
        mm.store_memory("IRIS diagnostics test entry — safe to ignore.")
        results = mm.retrieve_memory("diagnostics test")
        count   = len(results)
        return True, f"Store ✓ · Retrieve ✓ · {count} result(s)"
    except Exception as e:
        return False, str(e)


def check_tools(container) -> dict[str, tuple[bool, str]]:
    from ui.utils.prefs import is_tool_enabled
    results: dict[str, tuple[bool, str]] = {}
    safe_queries = {
        "calculator":      "calculate 1 + 1",
        "file_reader":     "read README.md",
        "project_scanner": "scan .",
    }
    for name, tool in container.tool_manager.tools.items():
        if not is_tool_enabled(name):
            results[name] = (None, "disabled")
            continue
        query = safe_queries.get(name, "test")
        try:
            out = tool.execute(query)
            results[name] = (True, str(out)[:60] if out else "empty response")
        except Exception as e:
            results[name] = (False, str(e)[:80])
    return results


def check_voice() -> tuple[bool, str]:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.stop()
        return True, "TTS engine initialised successfully."
    except Exception as e:
        return False, str(e)


# ── Public render ─────────────────────────────────────────────────────────────

def render_diagnostics() -> None:
    """Render the full diagnostics panel with run buttons."""
    from ui.utils.session import get_container
    from ui.utils.prefs   import get_pref

    st.markdown("### 🔬 Diagnostics")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "Run health checks against each IRIS subsystem.</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    run_ollama = col1.button("🤖 Ollama",   key="diag_ollama",  use_container_width=True)
    run_memory = col2.button("🧠 Memory",   key="diag_memory",  use_container_width=True)
    run_tools  = col3.button("🔧 Tools",    key="diag_tools",   use_container_width=True)
    run_voice  = col4.button("🎙️ Voice",    key="diag_voice",   use_container_width=True)
    run_all    = col5.button("▶ All",       key="diag_all",     use_container_width=True,
                              type="primary")

    st.divider()

    try:
        container = get_container()
    except Exception as exc:
        _fail("Container", str(exc))
        return

    model = get_pref("model")

    # ── Ollama ────────────────────────────────────────────────────────────────
    if run_ollama or run_all:
        with st.spinner(f"Checking Ollama model `{model}`..."):
            ok, msg = check_ollama(model)
        (_ok if ok else _fail)(f"Ollama · {model}", msg)

    # ── Memory ────────────────────────────────────────────────────────────────
    if run_memory or run_all:
        with st.spinner("Testing memory..."):
            ok, msg = check_memory(container)
        (_ok if ok else _fail)("Memory subsystem", msg)

    # ── Tools ─────────────────────────────────────────────────────────────────
    if run_tools or run_all:
        with st.spinner("Testing tools..."):
            tool_results = check_tools(container)
        for name, (ok, msg) in tool_results.items():
            if ok is None:
                _warn(f"Tool · {name}", msg)
            elif ok:
                _ok(f"Tool · {name}", msg)
            else:
                _fail(f"Tool · {name}", msg)

    # ── Voice ─────────────────────────────────────────────────────────────────
    if run_voice or run_all:
        with st.spinner("Testing voice engine..."):
            ok, msg = check_voice()
        (_ok if ok else _fail)("Voice (TTS engine)", msg)
