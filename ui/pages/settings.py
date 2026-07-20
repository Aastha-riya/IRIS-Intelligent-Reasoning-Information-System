"""
ui/pages/settings.py

Settings page — Steps 8–13 complete implementation.

Tabs:
    🎨 Appearance   — dark/light/system, accent, font size, compact mode
    🤖 AI Model     — model selection, temperature, max tokens, connection test
    🧠 Agent        — reflection/planner/workflow toggles, auto-memory
    💾 Memory       — context window, history limits, live stats
    🎙️ Voice        — enable/disable, speed, volume, test
    📊 System       — CPU, RAM, uptime, loaded tools, active conversations
    🔬 Diagnostics  — check Ollama / memory / tools / voice / all
    🗂️ Config        — save/load/reset/import/export settings.json
    🔒 Security     — clear cache, delete temp files, reset memory/conversations
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile

import streamlit as st

from ui.components.diagnostics   import render_diagnostics
from ui.components.settings_panel import render_appearance_settings, inject_appearance_css
from ui.components.system_info   import render_system_info
from ui.utils.session            import get_container
from ui.utils.prefs              import (
    get_pref, set_pref, reset_prefs, save_prefs, load_prefs, get_all_prefs,
)
import config.settings as cfg


# ── Model descriptions ────────────────────────────────────────────────────────

_MODEL_DESC = {
    "llama3.2": "Meta Llama 3.2 — fast and capable.",
    "llama3.1": "Meta Llama 3.1 — larger context window.",
    "mistral":  "Mistral 7B — efficient and multilingual.",
    "gemma2":   "Google Gemma 2 — strong reasoning.",
    "phi3":     "Microsoft Phi-3 — small but capable.",
}


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    # Apply dynamic appearance CSS each render
    inject_appearance_css()

    st.markdown("## ⚙️ Settings")
    st.markdown(
        '<p style="color:#8b949e;">Configure IRIS. '
        'Changes apply immediately; persistent settings are saved to '
        '<code>ui/config/settings.json</code>.</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    tabs = st.tabs([
        "🎨 Appearance",
        "🤖 AI Model",
        "🧠 Agent",
        "💾 Memory",
        "🎙️ Voice",
        "📊 System",
        "🔬 Diagnostics",
        "🗂️ Config",
        "🔒 Security",
    ])

    with tabs[0]:
        render_appearance_settings()

    with tabs[1]:
        _tab_model()

    with tabs[2]:
        _tab_agent()

    with tabs[3]:
        _tab_memory()

    with tabs[4]:
        _tab_voice()

    with tabs[5]:
        render_system_info()

    with tabs[6]:
        render_diagnostics()

    with tabs[7]:
        _tab_config()

    with tabs[8]:
        _tab_security()


# ── Tab: AI Model ─────────────────────────────────────────────────────────────

def _tab_model() -> None:
    st.markdown("### 🤖 AI Model")

    available = _get_ollama_models()
    current   = get_pref("model")

    if available:
        idx      = available.index(current) if current in available else 0
        selected = st.selectbox("Active model", available, index=idx,
                                help="Locally pulled Ollama models.")
        set_pref("model", selected)
        if selected in _MODEL_DESC:
            st.caption(_MODEL_DESC[selected])
    else:
        manual = st.text_input("Model name (manual)", value=current,
                               key="model_manual_input")
        if manual:
            set_pref("model", manual)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        temp = st.slider("Temperature", 0.0, 2.0,
                         float(get_pref("temperature")), 0.05,
                         help="0 = deterministic · 1 = creative")
        set_pref("temperature", temp)
    with col2:
        tok = st.slider("Max tokens", 256, 8192,
                        int(get_pref("max_tokens")), 256)
        set_pref("max_tokens", tok)

    st.divider()
    if st.button("🔗 Test connection", key="settings_test_conn"):
        with st.spinner(f"Connecting to `{get_pref('model')}`..."):
            ok, msg = _test_ollama(get_pref("model"))
        (st.success if ok else st.error)(("✅ " if ok else "❌ ") + msg)


# ── Tab: Agent ────────────────────────────────────────────────────────────────

def _tab_agent() -> None:
    st.markdown("### 🧠 Agent Behaviour")

    col1, col2 = st.columns(2)
    with col1:
        set_pref("reflection_enabled",
                 st.toggle("Reflection engine", get_pref("reflection_enabled")))
        set_pref("planner_enabled",
                 st.toggle("Planner", get_pref("planner_enabled")))
    with col2:
        set_pref("workflow_enabled",
                 st.toggle("Workflow engine", get_pref("workflow_enabled")))
        set_pref("auto_memory",
                 st.toggle("Auto-save to memory", get_pref("auto_memory")))

    st.divider()
    st.caption(
        "Disabling a module makes the agent fall back to simpler strategies "
        "(e.g. direct LLM answer). The modules stay loaded."
    )


# ── Tab: Memory ───────────────────────────────────────────────────────────────

def _tab_memory() -> None:
    st.markdown("### 💾 Memory Settings")

    col1, col2, col3 = st.columns(3)
    with col1:
        set_pref("max_history",
                 st.number_input("Max history turns", 5, 200,
                                 int(get_pref("max_history")), 5))
    with col2:
        set_pref("max_context_history",
                 st.number_input("Context window (turns)", 1, 50,
                                 int(get_pref("max_context_history")), 1))
    with col3:
        set_pref("max_context_memories",
                 st.number_input("RAG memories / prompt", 0, 20,
                                 int(get_pref("max_context_memories")), 1))

    st.divider()
    st.markdown("**Live stats**")
    try:
        mm = get_container().memory_manager
        c1, c2 = st.columns(2)
        c1.metric("Turns stored",    len(mm._history))
        c2.metric("Vectors indexed", mm._vector_store.size())
    except Exception:
        st.caption("Memory stats unavailable.")


# ── Tab: Voice ────────────────────────────────────────────────────────────────

def _tab_voice() -> None:
    st.markdown("### 🎙️ Voice Settings")

    col1, col2 = st.columns(2)
    with col1:
        ve = st.toggle("Enable voice output", get_pref("voice_enabled"))
        set_pref("voice_enabled", ve)
        set_pref("auto_speak",
                 st.toggle("Auto-speak responses", get_pref("auto_speak"),
                           disabled=not ve))
    with col2:
        set_pref("voice_speed",
                 st.slider("Speed (WPM)", 80, 300,
                           int(get_pref("voice_speed")), 10, disabled=not ve))
        set_pref("voice_volume",
                 st.slider("Volume", 0.0, 1.0,
                           float(get_pref("voice_volume")), 0.1, disabled=not ve))

    if ve:
        st.divider()
        phrase = st.text_input("Test phrase", "Hello, I am IRIS.", key="voice_test_phrase")
        if st.button("🔊 Test voice", key="settings_voice_test"):
            _test_voice(phrase, int(get_pref("voice_speed")))


# ── Tab: Config (Step 11) ─────────────────────────────────────────────────────

def _tab_config() -> None:
    st.markdown("### 🗂️ Configuration")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "Settings are stored in <code>ui/config/settings.json</code> "
        "and survive browser restarts.</p>",
        unsafe_allow_html=True,
    )

    col_save, col_load, col_reset = st.columns(3)

    # ── Save ──────────────────────────────────────────────────────────────────
    with col_save:
        if st.button("💾 Save settings", key="cfg_save", use_container_width=True,
                     type="primary"):
            save_prefs()
            st.success("Settings saved to settings.json.")

    # ── Load ──────────────────────────────────────────────────────────────────
    with col_load:
        if st.button("📂 Load from disk", key="cfg_load", use_container_width=True):
            loaded = load_prefs()
            st.session_state["prefs"] = loaded
            st.success("Settings loaded from disk.")
            st.rerun()

    # ── Reset ─────────────────────────────────────────────────────────────────
    with col_reset:
        if st.button("↺ Reset defaults", key="cfg_reset", use_container_width=True):
            st.session_state["cfg_confirm_reset"] = True

    if st.session_state.get("cfg_confirm_reset"):
        st.warning("This will overwrite all settings with defaults.")
        cy, cn = st.columns(2)
        if cy.button("Confirm reset", key="cfg_reset_yes"):
            reset_prefs()
            st.success("Settings reset to defaults.")
            st.session_state.pop("cfg_confirm_reset", None)
            st.rerun()
        if cn.button("Cancel", key="cfg_reset_no"):
            st.session_state.pop("cfg_confirm_reset", None)
            st.rerun()

    st.divider()

    # ── Export config ─────────────────────────────────────────────────────────
    st.markdown("**Export configuration**")
    try:
        from ui.config.settings_io import export_config
        config_json = export_config()
        st.download_button(
            label     = "⬇ Export settings.json",
            data      = config_json.encode("utf-8"),
            file_name = "iris_settings.json",
            mime      = "application/json",
            key       = "cfg_export_btn",
        )
    except Exception as exc:
        st.error(f"Export unavailable: {exc}")

    st.divider()

    # ── Import config ─────────────────────────────────────────────────────────
    st.markdown("**Import configuration**")
    uploaded = st.file_uploader(
        "Upload settings JSON",
        type=["json"],
        key="cfg_import_file",
        label_visibility="collapsed",
    )
    if uploaded:
        try:
            from ui.config.settings_io import import_config
            json_str = uploaded.read().decode("utf-8")
            merged   = import_config(json_str)
            st.session_state["prefs"] = merged
            st.success("Configuration imported and applied.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    st.divider()

    # ── Current config preview ────────────────────────────────────────────────
    with st.expander("👁 View current configuration"):
        prefs = get_all_prefs()
        # Convert any sets to lists for display
        display = {k: list(v) if isinstance(v, set) else v for k, v in prefs.items()}
        st.json(display)


# ── Tab: Security (Step 12) ───────────────────────────────────────────────────

def _tab_security() -> None:
    st.markdown("### 🔒 Security & Cleanup")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "These actions help protect privacy and free up disk space. "
        "Most are permanent.</p>",
        unsafe_allow_html=True,
    )

    # ── Clear cache ───────────────────────────────────────────────────────────
    st.markdown("#### Clear Cache")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ Clear embedding cache", key="sec_clear_embed",
                     use_container_width=True):
            try:
                get_container().memory_manager._embedder.clear_cache()
                st.success("Embedding cache cleared.")
            except Exception as e:
                st.error(str(e))

    with col2:
        if st.button("🗑️ Clear Streamlit cache", key="sec_clear_st",
                     use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Streamlit caches cleared.")

    st.divider()

    # ── Delete temporary files ────────────────────────────────────────────────
    st.markdown("#### Delete Temporary Files")
    if st.button("🗑️ Delete temp files", key="sec_del_tmp",
                 use_container_width=False):
        count = _delete_temp_files()
        st.success(f"Deleted {count} temporary file(s).")

    st.divider()

    # ── Reset memory ──────────────────────────────────────────────────────────
    st.markdown("#### Reset Memory")
    if st.button("⚠️ Reset all memory", key="sec_reset_mem"):
        st.session_state["sec_confirm_mem"] = True

    if st.session_state.get("sec_confirm_mem"):
        st.error("This permanently erases all conversation history and vector memories.")
        cy, cn = st.columns(2)
        if cy.button("Yes, reset memory", key="sec_mem_yes"):
            try:
                get_container().memory_manager.clear_memory()
                st.success("Memory reset.")
            except Exception as e:
                st.error(str(e))
            st.session_state.pop("sec_confirm_mem", None)
            st.rerun()
        if cn.button("Cancel", key="sec_mem_no"):
            st.session_state.pop("sec_confirm_mem", None)
            st.rerun()

    st.divider()

    # ── Reset conversations ───────────────────────────────────────────────────
    st.markdown("#### Reset Conversations")
    if st.button("⚠️ Reset all conversations", key="sec_reset_conv"):
        st.session_state["sec_confirm_conv"] = True

    if st.session_state.get("sec_confirm_conv"):
        st.error("This permanently deletes every conversation in this session.")
        cy2, cn2 = st.columns(2)
        if cy2.button("Yes, reset conversations", key="sec_conv_yes"):
            st.session_state.pop("conversations", None)
            st.session_state.pop("active_conv_id", None)
            st.session_state.pop("sec_confirm_conv", None)
            st.success("All conversations reset.")
            st.rerun()
        if cn2.button("Cancel", key="sec_conv_no"):
            st.session_state.pop("sec_confirm_conv", None)
            st.rerun()


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_ollama_models() -> list[str]:
    try:
        import ollama
        result = ollama.list()
        return [m["name"] for m in result.get("models", [])]
    except Exception:
        return [cfg.DEFAULT_MODEL]


def _test_ollama(model: str) -> tuple[bool, str]:
    try:
        import ollama
        resp  = ollama.chat(
            model    = model,
            messages = [{"role": "user", "content": "Reply with: OK"}],
        )
        reply = resp["message"]["content"].strip()[:60]
        return True, f"Model `{model}` responded: {reply}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def _test_voice(text: str, speed: int) -> None:
    import threading
    def _run():
        try:
            from voice.speak import Speaker
            sp = Speaker()
            sp.engine.setProperty("rate", speed)
            sp.speak(text[:200])
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def _delete_temp_files() -> int:
    """Delete IRIS-related temp files from the system temp directory."""
    count = 0
    tmp   = tempfile.gettempdir()
    for name in os.listdir(tmp):
        if name.startswith("iris_") or name.startswith("streamlit_"):
            try:
                path = os.path.join(tmp, name)
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                count += 1
            except Exception:
                pass
    return count
