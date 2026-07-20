"""
ui/pages/settings.py

Settings page — Phase 4 full implementation.

Sections:
    General        — theme, streaming, timestamps, workflow panel
    AI Model       — Ollama model selection, temperature, tokens, test connection
    Agent          — toggles for reflection, planner, workflow, auto-memory
    Memory         — context window, history size, memory limit
    Voice          — enable/disable, speed, auto-speak
    Advanced       — system info, reset, danger zone
"""

from __future__ import annotations

import streamlit as st

from ui.utils.session import get_container
from ui.utils.prefs   import get_pref, set_pref, reset_prefs
import config.settings as cfg


# ── Tool descriptions ─────────────────────────────────────────────────────────

_MODEL_DESCRIPTIONS = {
    "llama3.2": "Meta Llama 3.2 — fast, capable, great for most tasks.",
    "llama3.1": "Meta Llama 3.1 — larger context window.",
    "mistral":  "Mistral 7B — efficient and multilingual.",
    "gemma2":   "Google Gemma 2 — strong reasoning.",
    "phi3":     "Microsoft Phi-3 — small but capable.",
}


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("## ⚙️ Settings")
    st.markdown(
        '<p style="color:#8b949e;">Configure IRIS behaviour. '
        'Changes apply immediately for this session.</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    tab_general, tab_model, tab_agent, tab_memory, tab_voice, tab_advanced = st.tabs([
        "🎨 General",
        "🤖 AI Model",
        "🧠 Agent",
        "💾 Memory",
        "🎙️ Voice",
        "⚠️ Advanced",
    ])

    with tab_general:
        _section_general()

    with tab_model:
        _section_model()

    with tab_agent:
        _section_agent()

    with tab_memory:
        _section_memory()

    with tab_voice:
        _section_voice()

    with tab_advanced:
        _section_advanced()


# ── Section: General ──────────────────────────────────────────────────────────

def _section_general() -> None:
    st.subheader("🎨 General")

    col1, col2 = st.columns(2)

    with col1:
        stream = st.toggle(
            "Stream responses",
            value=get_pref("stream_responses"),
            help="Show response word-by-word instead of all at once.",
        )
        set_pref("stream_responses", stream)

        show_wf = st.toggle(
            "Show workflow panel",
            value=get_pref("show_workflow_panel"),
            help="Display the task timeline after multi-step responses.",
        )
        set_pref("show_workflow_panel", show_wf)

    with col2:
        timestamps = st.toggle(
            "Show timestamps",
            value=get_pref("show_timestamps"),
            help="Display message timestamps in the chat.",
        )
        set_pref("show_timestamps", timestamps)

        theme = st.selectbox(
            "Theme",
            ["dark", "light"],
            index=0 if get_pref("theme") == "dark" else 1,
        )
        set_pref("theme", theme)

    st.caption("Theme changes require a page reload to take full effect.")


# ── Section: AI Model ─────────────────────────────────────────────────────────

def _section_model() -> None:
    st.subheader("🤖 AI Model")

    # ── Model selection ───────────────────────────────────────────────────────
    available_models = _get_ollama_models()
    current_model    = get_pref("model")

    if available_models:
        idx = available_models.index(current_model) if current_model in available_models else 0
        selected = st.selectbox(
            "Active model",
            available_models,
            index=idx,
            help="Models pulled in Ollama. Run 'ollama list' to see all.",
        )
        set_pref("model", selected)
        if selected in _MODEL_DESCRIPTIONS:
            st.caption(_MODEL_DESCRIPTIONS[selected])
    else:
        st.text_input("Model name", value=current_model, key="model_name_input",
                      help="Ollama not reachable — enter model name manually.")
        if st.session_state.get("model_name_input"):
            set_pref("model", st.session_state["model_name_input"])

    st.divider()

    # ── Parameters ────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        temp = st.slider(
            "Temperature",
            min_value=0.0, max_value=2.0,
            value=float(get_pref("temperature")),
            step=0.05,
            help="0 = deterministic, 1 = creative, 2 = very creative.",
        )
        set_pref("temperature", temp)

    with col2:
        tokens = st.slider(
            "Max tokens",
            min_value=256, max_value=8192,
            value=int(get_pref("max_tokens")),
            step=256,
            help="Maximum response length in tokens.",
        )
        set_pref("max_tokens", tokens)

    st.divider()

    # ── Connection test ───────────────────────────────────────────────────────
    st.markdown("**Test model connection**")
    if st.button("🔗 Test connection", key="test_model_btn"):
        with st.spinner(f"Connecting to `{get_pref('model')}`..."):
            ok, msg = _test_ollama_connection(get_pref("model"))
        if ok:
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ {msg}")


# ── Section: Agent ────────────────────────────────────────────────────────────

def _section_agent() -> None:
    st.subheader("🧠 Agent Behaviour")

    col1, col2 = st.columns(2)

    with col1:
        refl = st.toggle(
            "Reflection engine",
            value=get_pref("reflection_enabled"),
            help="Evaluate task results and retry/replan on failure.",
        )
        set_pref("reflection_enabled", refl)

        plan = st.toggle(
            "Planner",
            value=get_pref("planner_enabled"),
            help="Decompose complex goals into multi-step plans.",
        )
        set_pref("planner_enabled", plan)

    with col2:
        wflow = st.toggle(
            "Workflow engine",
            value=get_pref("workflow_enabled"),
            help="Execute plans via the full Planner → Executor → Reflection pipeline.",
        )
        set_pref("workflow_enabled", wflow)

        auto_mem = st.toggle(
            "Auto-save to memory",
            value=get_pref("auto_memory"),
            help="Automatically store completed goals and outcomes in semantic memory.",
        )
        set_pref("auto_memory", auto_mem)

    st.divider()
    st.caption(
        "ℹ️  These toggles control IRIS behaviour for this session. "
        "The underlying modules are still loaded — disabling them means the agent "
        "will fall back to simpler strategies (e.g. direct LLM answer)."
    )


# ── Section: Memory ───────────────────────────────────────────────────────────

def _section_memory() -> None:
    st.subheader("💾 Memory Settings")

    col1, col2, col3 = st.columns(3)

    with col1:
        mh = st.number_input(
            "Max history turns (storage)",
            min_value=5, max_value=200,
            value=int(get_pref("max_history")),
            step=5,
            help="How many conversation turns are kept on disk.",
        )
        set_pref("max_history", mh)

    with col2:
        mch = st.number_input(
            "Context history (LLM window)",
            min_value=1, max_value=50,
            value=int(get_pref("max_context_history")),
            step=1,
            help="Recent turns injected into each LLM prompt.",
        )
        set_pref("max_context_history", mch)

    with col3:
        mcm = st.number_input(
            "Context memories (RAG)",
            min_value=0, max_value=20,
            value=int(get_pref("max_context_memories")),
            step=1,
            help="Semantic memories retrieved and injected per prompt.",
        )
        set_pref("max_context_memories", mcm)

    st.divider()

    # ── Live memory stats ─────────────────────────────────────────────────────
    st.markdown("**Live memory stats**")
    try:
        mm = get_container().memory_manager
        c1, c2, c3 = st.columns(3)
        c1.metric("Turns stored",    len(mm._history))
        c2.metric("Vectors indexed", mm._vector_store.size())
        c3.metric("Files on disk",   3)   # history, metadata, summary
    except Exception:
        st.caption("Memory stats unavailable.")


# ── Section: Voice ────────────────────────────────────────────────────────────

def _section_voice() -> None:
    st.subheader("🎙️ Voice Settings")

    col1, col2 = st.columns(2)

    with col1:
        v_enabled = st.toggle(
            "Enable voice output",
            value=get_pref("voice_enabled"),
            help="Allow IRIS to speak responses using text-to-speech.",
        )
        set_pref("voice_enabled", v_enabled)

        auto_speak = st.toggle(
            "Auto-speak responses",
            value=get_pref("auto_speak"),
            help="Automatically speak every assistant response.",
            disabled=not v_enabled,
        )
        set_pref("auto_speak", auto_speak)

    with col2:
        speed = st.slider(
            "Speech speed (WPM)",
            min_value=80, max_value=300,
            value=int(get_pref("voice_speed")),
            step=10,
            disabled=not v_enabled,
            help="Words per minute for text-to-speech.",
        )
        set_pref("voice_speed", speed)

        vol = st.slider(
            "Volume",
            min_value=0.0, max_value=1.0,
            value=float(get_pref("voice_volume")),
            step=0.1,
            disabled=not v_enabled,
        )
        set_pref("voice_volume", vol)

    st.divider()

    # ── Voice test ────────────────────────────────────────────────────────────
    if v_enabled:
        test_text = st.text_input(
            "Test phrase",
            value="Hello, I am IRIS.",
            key="voice_test_text",
        )
        if st.button("🔊 Test voice", key="test_voice_btn"):
            with st.spinner("Speaking..."):
                _test_voice(test_text, speed)


# ── Section: Advanced ─────────────────────────────────────────────────────────

def _section_advanced() -> None:
    st.subheader("⚠️ Advanced")

    # ── System info ───────────────────────────────────────────────────────────
    st.markdown("**System information**")
    try:
        container = get_container()
        st.json({
            "agent_status":     container.agent.status.value,
            "model":            get_pref("model"),
            "tools":            list(container.tool_manager.tools.keys()),
            "history_file":     cfg.HISTORY_FILE,
            "vector_index":     cfg.VECTOR_INDEX_FILE,
            "log_file":         cfg.LOG_FILE,
            "reflection":       get_pref("reflection_enabled"),
            "planner":          get_pref("planner_enabled"),
            "workflow":         get_pref("workflow_enabled"),
        })
    except Exception as exc:
        st.caption(f"System info unavailable: {exc}")

    st.divider()

    # ── Reset preferences ─────────────────────────────────────────────────────
    st.markdown("**Reset preferences**")
    if st.button("↺ Reset all settings to defaults", key="reset_prefs_btn"):
        reset_prefs()
        st.success("Settings reset to defaults.")
        st.rerun()

    st.divider()

    # ── Danger zone ───────────────────────────────────────────────────────────
    st.markdown("**Danger zone**")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;">'
        "These actions are permanent and cannot be undone.</p>",
        unsafe_allow_html=True,
    )

    col_mem, col_conv = st.columns(2)

    with col_mem:
        if st.button("🗑️ Clear all memory", key="adv_clear_mem"):
            st.session_state["_adv_confirm_mem"] = True

        if st.session_state.get("_adv_confirm_mem"):
            st.warning("This will erase all conversation history and vector memories.")
            cy, cn = st.columns(2)
            if cy.button("Confirm", key="adv_mem_yes"):
                try:
                    get_container().memory_manager.clear_memory()
                    st.success("Memory cleared.")
                except Exception as e:
                    st.error(str(e))
                st.session_state.pop("_adv_confirm_mem", None)
                st.rerun()
            if cn.button("Cancel", key="adv_mem_no"):
                st.session_state.pop("_adv_confirm_mem", None)
                st.rerun()

    with col_conv:
        if st.button("🗑️ Clear all conversations", key="adv_clear_conv"):
            st.session_state["_adv_confirm_conv"] = True

        if st.session_state.get("_adv_confirm_conv"):
            st.warning("This will delete every conversation from this session.")
            cy2, cn2 = st.columns(2)
            if cy2.button("Confirm", key="adv_conv_yes"):
                st.session_state.pop("conversations", None)
                st.session_state.pop("active_conv_id", None)
                st.session_state.pop("_adv_confirm_conv", None)
                st.success("Conversations cleared.")
                st.rerun()
            if cn2.button("Cancel", key="adv_conv_no"):
                st.session_state.pop("_adv_confirm_conv", None)
                st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_ollama_models() -> list[str]:
    """Return a list of locally available Ollama models."""
    try:
        import ollama
        models = ollama.list()
        return [m["name"] for m in models.get("models", [])]
    except Exception:
        # Fallback: return a known-good list
        return [cfg.DEFAULT_MODEL]


def _test_ollama_connection(model: str) -> tuple[bool, str]:
    """Send a minimal chat to test the model connection."""
    try:
        import ollama
        response = ollama.chat(
            model    = model,
            messages = [{"role": "user", "content": "Reply with just: OK"}],
        )
        reply = response["message"]["content"].strip()
        return True, f"Model `{model}` responded: {reply[:60]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def _test_voice(text: str, speed: int) -> None:
    """Speak a test phrase using the existing Speaker."""
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
