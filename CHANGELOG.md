# Changelog

All notable changes to IRIS are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0] — 2026-07-20

### Added — Core Agent
- `AutonomousAgent` with Observe → Reason → Plan → Execute → Reflect → Learn loop
- `WorkflowEngine` — orchestrates Planner → Executor → ReflectionEngine
- `Planner` — LLM-powered JSON task decomposition with validation and retry
- `Executor` — dependency-ordered task runner with retry and event publishing
- `ReflectionEngine` — error classification (transient/permanent), retry/replan/abort decisions
- `ProgressTracker` — per-plan task status monitoring

### Added — Memory
- `MemoryManager` — single facade for all memory operations
- `Storage` — JSON file I/O for history, metadata, summary
- `ConversationHistory` — in-memory turn model with legacy migration
- `EmbeddingService` — SentenceTransformer wrapper with caching
- `VectorStore` — FAISS-backed persistent vector database
- `Retriever` — semantic search with similarity + importance + recency ranking
- `ContextBuilder` — RAG prompt assembly (system + memories + history + query)

### Added — Tools
- `Calculator` — math expression evaluator
- `FileReader` — reads local file contents
- `ProjectScanner` — source file discovery
- `Internet` — DuckDuckGo web search

### Added — Models
- `Task`, `Plan`, `TaskResult` dataclasses with full serialisation
- `TaskStatus` (7 states) and `TaskPriority` (4 levels) enums

### Added — Streamlit UI (Phases 1–5)
- Dashboard with health metrics, recent conversations, quick actions
- Chat page — streaming, file upload, voice input, workflow timeline
- Memory Manager — browse, search, import, delete
- Conversation Manager — pin, search, export (TXT/MD/PDF), import
- Workflow Runner — manual goal execution with task timeline
- Tools Manager — enable/disable, health check, direct test
- Logging Dashboard — live log viewer with filter, search, download
- Settings — 9 tabs covering appearance, model, agent, memory, voice, diagnostics, config I/O, security
- Persistent settings via `ui/config/settings.json`

### Added — Packaging
- `Dockerfile` + `docker-compose.yml` for containerised deployment
- `.env.example` for environment variable configuration
- `.streamlit/config.toml` for Streamlit theme and server settings

---

## [0.9.0] — 2026-06-01 (Pre-release)

### Added
- Initial agent architecture (Planner, Executor, basic memory)
- Terminal-based IrisAssistant with keyboard and voice modes
- Basic tool system (Calculator, FileReader, ProjectScanner)
- Structured logging via `utils/logger.py`
- Dependency injection Container

---

[1.0.0]: https://github.com/your-username/IRIS/releases/tag/v1.0.0
[0.9.0]: https://github.com/your-username/IRIS/releases/tag/v0.9.0
