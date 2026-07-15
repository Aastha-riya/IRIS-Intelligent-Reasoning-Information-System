# IRIS — Intelligent Reasoning Information System

A modular, local-first AI assistant built in Python.  
IRIS runs entirely on your machine using Ollama — no cloud API keys required.

---

## Features

- **Conversational AI** — multi-turn chat with persistent memory
- **Voice I/O** — speak to IRIS and hear responses
- **Keyboard mode** — text-based interaction when audio isn't available
- **Tool system** — Calculator, File Reader, Project Scanner, Web Search
- **Semantic memory** — vector-based retrieval of past context (FAISS)
- **Structured logging** — timestamped logs to terminal and `logs/iris.log`
- **Dependency injection** — clean, testable architecture via a central Container

---

## Architecture

```
main.py
  └── Startup.initialize()
        └── Container()          ← all objects built once here
              ├── Memory
              ├── LLM(memory)
              ├── Reasoner
              ├── Planner
              ├── Executor
              ├── ToolManager
              ├── Speaker
              ├── Listener
              └── EventBus
  └── IrisAssistant(container)
        └── .start()             ← session loop lives here
```

Every module receives its dependencies — nothing self-constructs.

---

## Project Structure

```
IRIS/
├── app/
│   ├── container.py       # Creates all shared services
│   └── startup.py         # Bootstraps the application
├── brain/
│   ├── llm.py             # Ollama LLM wrapper
│   ├── planner.py         # Builds structured execution plans
│   └── reasoner.py        # Keyword-based intent classifier
├── core/
│   ├── assistant.py       # Main session loop
│   ├── events.py          # Pub/sub event bus
│   ├── executor.py        # Executes planner output
│   └── router.py          # Routes queries to tools or LLM
├── memory/
│   ├── database.py        # JSON-based conversation persistence
│   └── vector_store.py    # FAISS semantic memory
├── tools/
│   ├── base_tool.py       # Abstract base class for all tools
│   ├── calculator.py      # Math expression evaluator
│   ├── file_reader.py     # Reads file contents
│   ├── internet.py        # DuckDuckGo web search
│   ├── project_scanner.py # Scans project directories
│   └── tool_manager.py    # Tool registry and dispatcher
├── voice/
│   ├── listen.py          # Microphone speech recognition
│   └── speak.py           # Text-to-speech output
├── vision/
│   └── camera.py          # (planned) Camera/image input
├── config/
│   └── settings.py        # All constants and configuration
├── utils/
│   └── logger.py          # Application-wide structured logger
├── logs/
│   └── iris.log           # Runtime log file
├── tests/
│   ├── test_llm.py
│   ├── test_memory.py
│   └── test_tools.py
├── data/
│   └── memory.json        # Persistent conversation history
├── requirements.txt
└── main.py
```

---

## Installation

**Prerequisites:** Python 3.11+, [Ollama](https://ollama.com) installed and running.

```bash
# 1. Pull the model
ollama pull llama3.2

# 2. Clone the repository
git clone https://github.com/your-username/IRIS.git
cd IRIS

# 3. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run IRIS
python main.py
```

---

## Usage

On startup, choose your input mode:

```
========== IRIS ==========
1. Keyboard Mode
2. Voice Mode
==========================
```

**Example queries:**

| Input | Tool used |
|---|---|
| `calculate 52 * 73` | Calculator |
| `read src/main.py` | File Reader |
| `scan ./my_project` | Project Scanner |
| `search Python async tutorial` | Internet |
| `What is machine learning?` | LLM |

Type `exit`, `quit`, or `bye` to end the session.

---

## Configuration

All tuneable values are in `config/settings.py`:

| Constant | Default | Purpose |
|---|---|---|
| `DEFAULT_MODEL` | `llama3.2` | Ollama model name |
| `MAX_HISTORY` | `50` | Conversation turns kept in memory |
| `LLM_TEMPERATURE` | `0.7` | Response creativity |
| `MAX_TOKENS` | `2048` | Max tokens per response |
| `VOICE_SPEED` | `175` | TTS words per minute |
| `VECTOR_SEARCH_TOP_K` | `3` | Memories retrieved per query |

---

## Future Roadmap

- [ ] Vision module — camera/image input
- [ ] Plugin system — hot-loadable tool plugins
- [ ] Browser tool — headless web navigation
- [ ] GitHub integration — repo summarisation and PR review
- [ ] Email / Calendar — scheduling and notifications
- [ ] GUI / Web interface
- [ ] Wake-word activation

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

Please follow the existing naming conventions and add docstrings to all public classes and functions.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
