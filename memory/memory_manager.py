"""
memory/memory_manager.py

The single facade for all memory operations in IRIS.

The rest of the application only ever calls MemoryManager.
No other module touches JSON files, FAISS, or embeddings directly.

Full pipeline:
    User query
        ↓
    retrieve_memory()     → Retriever → EmbeddingService → VectorStore
        ↓
    load_history()        → ConversationHistory → Storage (history.json)
        ↓
    [passed to ContextBuilder in LLM]
        ↓
    save_conversation()   → ConversationHistory + Storage + VectorStore
        ↓
    _update_metadata()    → Storage (metadata.json)
"""

from datetime import datetime

from config.settings import HISTORY_FILE, METADATA_FILE, SUMMARY_FILE, MAX_HISTORY, VECTOR_META_FILE, MAX_CONTEXT_HISTORY
from memory.context_builder import ContextBuilder
from memory.embeddings import EmbeddingService
from memory.history import ConversationHistory
from memory.retriever import Retriever, RetrievedMemory
from memory.storage import Storage
from memory.summarizer import Summarizer
from memory.vector_store import VectorStore
from utils.logger import logger


class MemoryManager:
    """
    Coordinates all memory subsystems.
    The only memory interface the rest of the application should use.
    """

    def __init__(self) -> None:
        # ── Storage (JSON I/O) ─────────────────────────────────────────────────
        self._history_storage  = Storage(HISTORY_FILE)
        self._summary_storage  = Storage(SUMMARY_FILE)
        self._metadata_storage = Storage(METADATA_FILE)

        # ── Conversation history (in-memory model) ────────────────────────────
        self._history = ConversationHistory(self._history_storage.read())

        # ── Semantic memory pipeline ──────────────────────────────────────────
        self._embedder     = EmbeddingService()
        self._vector_store = VectorStore()
        self._vector_store.initialize()          # load from disk or create fresh
        self._retriever    = Retriever(self._embedder, self._vector_store)

        # ── Context assembly ──────────────────────────────────────────────────
        self.context_builder = ContextBuilder()

        # ── Summarization (stub until LLM is wired in) ────────────────────────
        self._summarizer = Summarizer()

        # Seed the vector store with existing history on startup
        self._seed_vector_store()

        logger.info(f"MemoryManager ready — {len(self._history)} turns loaded.")

    # ── Conversation ──────────────────────────────────────────────────────────

    def save_conversation(self, user: str, assistant: str) -> None:
        """
        Persist one completed exchange.
        Updates: in-memory history, history.json, vector store, metadata.json.
        """
        # 1. Add to history model + persist to JSON
        turn = self._history.add(user, assistant)
        self._history_storage.append(turn)

        # 2. Embed and store both sides in the vector store for future retrieval
        combined = f"User: {user}\nAssistant: {assistant}"
        embedding = self._embedder.generate_embedding(combined)
        self._vector_store.add(embedding, {
            "text":       combined,
            "importance": 1.0,
        })

        # 3. Update session metadata
        self._update_metadata()
        logger.debug("MemoryManager: conversation saved.")

    def load_history(self, limit: int = MAX_CONTEXT_HISTORY) -> list[dict]:
        """
        Return the last `limit` turns as flat [{role, content}] message dicts,
        ready to pass directly into the LLM message list.
        """
        messages = self._history.recent(limit)
        logger.debug(f"MemoryManager: loaded {len(messages)} history messages.")
        return messages

    # ── Semantic retrieval ────────────────────────────────────────────────────

    def retrieve_memory(self, query: str) -> list[RetrievedMemory]:
        """
        Return the most semantically relevant past exchanges for the query,
        ranked by similarity + importance + recency.
        Used by build_context() to enrich the LLM prompt.
        """
        memories = self._retriever.retrieve(query)
        logger.info(f"Retrieved {len(memories)} memories.")
        return memories

    def store_memory(self, text: str) -> None:
        """
        Embed and store an arbitrary text string in the vector store.
        Use this for storing facts, notes, or tool results.
        """
        embedding = self._embedder.generate_embedding(text)
        self._vector_store.add(embedding, {"text": text, "importance": 1.0})
        logger.debug(f"MemoryManager: stored memory: '{text[:60]}'")

    # ── Context building ──────────────────────────────────────────────────────

    def build_context(self, user_query: str) -> list[dict]:
        """
        Assemble the full four-section message list for the LLM:
            [system prompt] + [memories] + [recent history] + [user query]

        This is the RAG pipeline entry point — called by LLM.chat().
        """
        recent_history    = self.load_history(MAX_CONTEXT_HISTORY)
        relevant_memories = self.retrieve_memory(user_query)
        return self.context_builder.build(user_query, recent_history, relevant_memories)

    # ── Summarization ─────────────────────────────────────────────────────────

    def summarize_memory(self) -> str:
        """
        Compress older turns into a summary paragraph.
        Stub until Summarizer.set_llm() is called during startup.
        """
        old_turns = self._history.all_turns()[:-MAX_HISTORY]
        summary = self._summarizer.summarize(old_turns)
        if summary:
            self._summary_storage.append({"summary": summary,
                                           "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            logger.info("MemoryManager: summary saved.")
        return summary

    # ── Maintenance ───────────────────────────────────────────────────────────

    def clear_memory(self) -> None:
        """Erase all conversation history, summaries, metadata, and vectors."""
        self._history.clear()
        self._history_storage.clear()
        self._summary_storage.clear()
        self._metadata_storage.clear()
        self._vector_store.reset()
        logger.info("MemoryManager: all memory cleared.")

    # ── Private ───────────────────────────────────────────────────────────────

    def _seed_vector_store(self) -> None:
        """
        On startup, if the index is empty (e.g. first run or after reset),
        embed all existing history turns so past conversations are searchable.
        Skipped if the index was already loaded from disk with existing vectors.
        """
        turns = self._history.all_turns()
        if not turns or self._vector_store.size() > 0:
            return

        for turn in turns:
            combined = f"User: {turn['user']}\nAssistant: {turn['assistant']}"
            embedding = self._embedder.generate_embedding(combined)
            self._vector_store.add(embedding, {
                "text":       combined,
                "importance": 1.0,
                "timestamp":  turn.get("time", "migrated"),
            })

        logger.info(f"MemoryManager: seeded vector store with {len(turns)} historical turns.")

    def _update_metadata(self) -> None:
        """Overwrite metadata.json with current session statistics."""
        stats = [{
            "total_turns":  len(self._history),
            "vector_size":  self._vector_store.size(),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }]
        self._metadata_storage.write(stats)
