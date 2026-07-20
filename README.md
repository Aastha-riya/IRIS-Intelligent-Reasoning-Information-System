# 🤖 IRIS — Intelligent Reasoning Information System

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black?logo=ollama)](https://ollama.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **modular, local-first AI assistant** built in Python.  
IRIS runs entirely on your machine using [Ollama](https://ollama.com) — no cloud API keys required.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **Autonomous Agent** | Observe → Reason → Plan → Execute → Reflect → Learn |
| 📋 **Multi-step Workflows** | Planner decomposes goals into validated task lists |
| 🔄 **Reflection Engine** | Automatically retries, replans, or aborts on failure |
| 💾 **Semantic Memory** | FAISS vector store with RAG-based context injection |
| 🔧 **Tool System** | Calculator, File Reader, Project Scanner, Web Search |
| 🎙️ **Voice I/O** | Speak to IRIS, hear responses via TTS |
| 📎 **File Upload** | Analyse PDF, DOCX, TXT, CSV, XLSX, images, ZIP |
| 🖥️ **Streamlit UI** | Professional 8-page dashboard with dark theme |
| 💬 **Conversation Manager** | Pin, search, export, import chats |
| 📊 **Settings Persistence** | All preferences saved to `ui/config/settings.json` |

---

## 🏗️ Architecture

```
main.py (terminal) / ui/app.py (browser)
    │
    ▼
IrisAssistant  ←── thin conductor, calls Agent only
    │
    ▼
AutonomousAgent
    ├── _observe()    → MemoryManager.retrieve_memory()
    ├── _reason()     → DIRECT | TOOL | PLAN | CLARIFY
    ├── _run_tool()   → ToolManager
    ├── _run_workflow() → WorkflowEngine
    │       ├── Planner.create_plan()
    │       ├── Executor.execute_plan()
    │       └── ReflectionEngine.reflect()
    └── _reflect_and_learn() → MemoryManager.store_memory()
```

---

## 📁 Project Structure

```
IRIS/
├── app/                 # Container (DI) + Startup
├── brain/               # LLM, Planner, Reasoner, Validator, Reflection
├── core/                # Agent, Assistant, Executor, Workflow, Events
├── memory/              # MemoryManager, Storage, History, Embeddings, VectorStore
├── models/              # Task, Plan, TaskResult, Enums
├── tools/               # Calculator, FileReader, ProjectScanner, Internet
├── voice/               # Speaker (TTS), Listener (STT)
├── config/              # settings.py (all constants)
├── utils/               # logger.py
├── ui/                  # Streamlit application
│   ├── app.py           # Entry point
│   ├── pages/           # Dashboard, Chat, Memory, Conversations, Workflow, Tools, Logs, Settings
│   ├── components/      # Reusable widgets
│   ├── utils/           # session.py, prefs.py, theme.py
│   └── config/          # settings.json, defaults.py
├── tests/               # Unit tests
├── logs/                # iris.log
├── memory/              # history.json, metadata.json, vector.index
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── main.py              # Terminal mode entry point
```

---

## 🚀 Installation

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) installed and running

### Quick Start

```bash
# 1. Clone
git clone https://github.com/your-username/IRIS.git
cd IRIS

# 2. Virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull a model
ollama pull llama3.2

# 5. Launch the UI
streamlit run ui/app.py

# OR run in terminal mode
python main.py
```

### Docker

```bash
docker compose up --build
# UI available at http://localhost:8501
# Ollama at http://localhost:11434
```

---

## 💡 Usage

### Browser UI
Open `http://localhost:8501` after running `streamlit run ui/app.py`.

**Example queries:**

| Input | What IRIS does |
|---|---|
| `What is machine learning?` | Direct LLM answer |
| `calculate 52 * 73` | Calculator tool |
| `read README.md` | File reader tool |
| `scan ./src` | Project scanner |
| `analyse this repository` | Full workflow: plan → execute → reflect |
| Upload a PDF + ask questions | File content injected into context |
| Click 🎤 | Voice input via microphone |

### Terminal Mode
```
python main.py
> Choose mode (1/2): 1
You: What is Python?
IRIS: Python is a high-level...
```

---

## ⚙️ Configuration

All settings in `config/settings.py`. UI preferences saved to `ui/config/settings.json`.

| Constant | Default | Purpose |
|---|---|---|
| `DEFAULT_MODEL` | `llama3.2` | Ollama model |
| `MAX_HISTORY` | `15` | Turns kept in storage |
| `MAX_CONTEXT_HISTORY` | `10` | Turns sent to LLM |
| `MAX_CONTEXT_MEMORIES` | `5` | RAG memories per prompt |
| `LLM_TEMPERATURE` | `0.7` | Response creativity |
| `VOICE_SPEED` | `175` | TTS words per minute |

---

## 🗺️ Roadmap

- [ ] Vision module (camera/image input)
- [ ] Browser tool (headless navigation)
- [ ] GitHub integration (repo analysis, PR review)
- [ ] Email / Calendar integration
- [ ] Plugin system
- [ ] Streaming token-by-token LLM responses
- [ ] Multi-agent collaboration

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Specific test files
python -m pytest tests/test_embeddings.py -v
python -m pytest tests/test_vector_store.py -v
python -m pytest tests/test_planner.py -v
python -m pytest tests/test_executor.py -v
python -m pytest tests/test_reflection.py -v
python -m pytest tests/test_workflow.py -v
python -m pytest tests/test_agent.py -v
```

---

## 🔧 Troubleshooting

**Ollama not connecting**
```bash
# Check Ollama is running
ollama list
# If not, start it
ollama serve
```

**Model not found**
```bash
ollama pull llama3.2
```

**Voice not working (Windows)**
```bash
pip install pipwin
pipwin install pyaudio
```

**FAISS import error**
```bash
pip install faiss-cpu
```

**Streamlit port in use**
```bash
streamlit run ui/app.py --server.port 8502
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Aastha Gupta** — Built as part of a B.Tech AIML internship project.

> IRIS demonstrates production-quality AI agent architecture:
> dependency injection, RAG memory, autonomous planning,
> reflection-driven self-correction, and a full Streamlit UI.
