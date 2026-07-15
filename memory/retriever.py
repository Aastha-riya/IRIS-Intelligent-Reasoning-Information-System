"""
memory/retriever.py

Semantic memory retrieval — the only module that performs memory search.

Single responsibility:
    query string  →  list[RetrievedMemory]   (ranked, filtered, structured)

Nothing else.  No LLM.  No JSON writes.  No conversation saving.
Only retrieval.

Full pipeline:
    User question
        ↓
    EmbeddingService      → question vector (float32)
        ↓
    VectorStore.search    → top-K raw candidates [{text, distance, timestamp, importance}]
        ↓
    Similarity filter     → drop candidates whose L2 distance > SIMILARITY_THRESHOLD
        ↓
    Ranking               → score = similarity_weight * (1 / (1 + distance))
                                   + importance_weight * importance
                                   + recency_weight   * recency_score
        ↓
    Top MAX_CONTEXT_MEMORIES results returned as RetrievedMemory objects

Architecture:
    MemoryManager
        ↓
    Retriever            ← this file
        ↓
    VectorStore → FAISS

The assistant never calls FAISS directly. MemoryManager is the only caller
of Retriever, and Retriever is the only caller of VectorStore.search().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from config.settings import (
    MAX_CONTEXT_MEMORIES,
    SIMILARITY_THRESHOLD,
    VECTOR_SEARCH_TOP_K,
)
from memory.embeddings import EmbeddingService
from memory.vector_store import VectorStore
from utils.logger import logger

# ── Ranking weights (must sum to 1.0) ────────────────────────────────────────
SIMILARITY_WEIGHT: float = 0.6   # How much raw vector similarity matters
IMPORTANCE_WEIGHT: float = 0.3   # How much the stored importance score matters
RECENCY_WEIGHT:    float = 0.1   # How much recency (age of memory) matters

# Recency decay: memories older than this many days score 0 on recency
RECENCY_MAX_DAYS: int = 30


# ── Memory object ─────────────────────────────────────────────────────────────

@dataclass
class RetrievedMemory:
    """
    A single retrieved memory with all metadata attached.
    Returned by Retriever.retrieve() — callers never see raw dicts or distances.

    Attributes:
        text:             The original stored text (e.g. "User: I love Java\\nAssistant: ...")
        similarity_score: Normalised similarity in [0, 1]. Higher = more similar.
        timestamp:        When the memory was stored (ISO-style string).
        importance:       Stored importance score in [0, 1].
        rank_score:       Final combined ranking score used for ordering.
    """
    text:             str
    similarity_score: float
    timestamp:        str   = field(default="unknown")
    importance:       float = field(default=1.0)
    rank_score:       float = field(default=0.0)

    def __str__(self) -> str:
        return self.text


# ── Retriever ─────────────────────────────────────────────────────────────────

class Retriever:
    """
    Finds, filters, and ranks semantically relevant memories for a query.

    Injected dependencies (never self-constructed):
        embedder:     EmbeddingService — converts query to vector
        vector_store: VectorStore      — FAISS search
    """

    def __init__(
        self,
        embedder: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._embedder     = embedder
        self._vector_store = vector_store

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int = VECTOR_SEARCH_TOP_K,
    ) -> list[RetrievedMemory]:
        """
        Return the most relevant stored memories for the query,
        ranked by a weighted combination of similarity, importance, and recency.

        Args:
            query: The user's question or statement.
            top_k: Maximum raw candidates to fetch from FAISS before ranking.

        Returns:
            Up to MAX_CONTEXT_MEMORIES RetrievedMemory objects, best first.
            Returns [] if the store is empty or nothing passes the threshold.
        """
        logger.info(f"Searching memory for: '{query[:60]}'")

        if self._vector_store.size() == 0:
            logger.info("No relevant memories found — vector store is empty.")
            return []

        # Step 1 — embed the query
        query_vector = self._embedder.generate_embedding(query)

        # Step 2 — fetch raw candidates from FAISS
        raw_candidates = self._vector_store.search(query_vector, top_k=top_k)
        logger.info(f"Retrieved {len(raw_candidates)} candidates from vector store.")

        # Step 3 — convert to RetrievedMemory, compute similarity, filter threshold
        candidates = self._build_candidates(raw_candidates)

        if not candidates:
            logger.info("No relevant memories found — all candidates below threshold.")
            return []

        # Step 4 — rank by combined score
        ranked = self._rank(candidates)

        # Step 5 — return top MAX_CONTEXT_MEMORIES
        results = ranked[:MAX_CONTEXT_MEMORIES]
        logger.info(f"Returning {len(results)} relevant memories.")
        return results

    def retrieve_as_strings(self, query: str) -> list[str]:
        """
        Convenience wrapper — returns plain text strings instead of objects.
        Used by ContextBuilder which only needs the text content.
        """
        return [m.text for m in self.retrieve(query)]

    # ── Private — pipeline stages ─────────────────────────────────────────────

    def _build_candidates(self, raw: list[dict]) -> list[RetrievedMemory]:
        """
        Convert raw VectorStore results to RetrievedMemory objects.
        Drops any result whose L2 distance exceeds SIMILARITY_THRESHOLD.

        L2 distance is converted to a normalised similarity score:
            similarity = 1 / (1 + distance)   →  range (0, 1], higher = closer
        """
        candidates: list[RetrievedMemory] = []

        for result in raw:
            distance = result.get("distance", float("inf"))

            # Similarity threshold: L2 distance must be ≤ threshold
            if distance > SIMILARITY_THRESHOLD:
                continue

            similarity_score = 1.0 / (1.0 + distance)   # normalise to (0, 1]

            candidates.append(RetrievedMemory(
                text             = result.get("text", ""),
                similarity_score = round(similarity_score, 4),
                timestamp        = result.get("timestamp", "unknown"),
                importance       = float(result.get("importance", 1.0)),
            ))

        return candidates

    def _rank(self, candidates: list[RetrievedMemory]) -> list[RetrievedMemory]:
        """
        Score each candidate with a weighted combination of:
            similarity  — how close the vector is to the query
            importance  — the stored importance value (0–1)
            recency     — how recently the memory was created (0–1, linear decay)

        Sort by rank_score descending (best first).
        """
        now = datetime.now()

        for memory in candidates:
            recency = self._recency_score(memory.timestamp, now)

            memory.rank_score = round(
                SIMILARITY_WEIGHT * memory.similarity_score
                + IMPORTANCE_WEIGHT * memory.importance
                + RECENCY_WEIGHT    * recency,
                4,
            )

        candidates.sort(key=lambda m: m.rank_score, reverse=True)
        return candidates

    @staticmethod
    def _recency_score(timestamp: str, now: datetime) -> float:
        """
        Convert a timestamp string to a recency score in [0, 1].

        Memories stored today score 1.0.
        Memories older than RECENCY_MAX_DAYS days score 0.0.
        Linear decay in between.
        """
        try:
            stored = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            age_days = (now - stored).days
            score = max(0.0, 1.0 - age_days / RECENCY_MAX_DAYS)
            return round(score, 4)
        except Exception:
            # Unknown or migrated timestamp — treat as neutral recency
            return 0.5
