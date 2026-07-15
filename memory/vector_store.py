"""
memory/vector_store.py

FAISS-backed vector database with persistence.

Single responsibility:
    add(vector, metadata)  →  store in FAISS + metadata.json
    search(vector, top_k)  →  return nearest neighbours
    save()                 →  write index to vector.index
    load()                 →  restore index from vector.index
    reset()                →  wipe everything and start fresh

Nothing else.  No LLM.  No conversation logic.  No embeddings generated here.
Receives ready-made float32 vectors from EmbeddingService via MemoryManager.

Files written:
    memory/vector.index       — FAISS binary index (vectors only)
    memory/vector_meta.json   — metadata for each vector:
        {
            "id":         0,
            "text":       "User: Hello\\nAssistant: Hi!",
            "timestamp":  "2026-07-14 21:10:05",
            "importance": 1.0
        }

Architecture:
    MemoryManager
        ↓
    EmbeddingService   (produces vectors)
        ↓
    VectorStore        (stores + searches vectors)
        ↓
    FAISS              (does the math)
"""

import json
import os
from datetime import datetime

import faiss
import numpy as np

from config.settings import (
    EMBEDDING_DIMENSION,
    VECTOR_INDEX_FILE,
    VECTOR_META_FILE,
    VECTOR_SEARCH_TOP_K,
)
from utils.logger import logger


class VectorStore:
    """
    Persistent FAISS vector database.

    Vectors and their metadata survive restarts — the index is saved to disk
    after every add() call and reloaded automatically on initialize().

    Usage (via MemoryManager — never call directly from elsewhere):
        store = VectorStore()
        store.initialize()
        store.add(embedding, {"text": "...", "importance": 1.0})
        results = store.search(query_embedding, top_k=5)
        store.reset()
    """

    def __init__(self) -> None:
        self._index: faiss.Index | None = None
        self._metadata: list[dict] = []   # parallel list — entry i matches vector i
        self._index_file = VECTOR_INDEX_FILE
        self._meta_file  = VECTOR_META_FILE
        self._ensure_directory()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """
        Load an existing index from disk, or create a new one if none exists.
        Call this once at startup — MemoryManager handles the call.

        On corruption: logs an error, wipes the broken files, and starts fresh.
        """
        if os.path.exists(self._index_file):
            self.load()
        else:
            self._create_empty_index()
            logger.info("VectorStore: created new FAISS index.")

    # ── Core API ──────────────────────────────────────────────────────────────

    def add(self, embedding: np.ndarray, metadata: dict) -> int:
        """
        Store a single vector and its associated metadata.

        Args:
            embedding: float32 array of shape (EMBEDDING_DIMENSION,).
            metadata:  Dict with at minimum a 'text' key.
                       'timestamp' and 'importance' are added automatically
                       if not supplied.

        Returns:
            The integer ID assigned to this vector.

        Raises:
            RuntimeError: If the index has not been initialized.
            ValueError:   If the embedding has the wrong shape.
        """
        self._require_initialized()
        self._validate_embedding(embedding)

        vector_id = len(self._metadata)

        # Normalise metadata
        entry = {
            "id":         vector_id,
            "text":       metadata.get("text", ""),
            "timestamp":  metadata.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "importance": float(metadata.get("importance", 1.0)),
        }

        self._index.add(embedding.reshape(1, -1))
        self._metadata.append(entry)
        self._save_metadata()
        self.save()

        logger.info(f"VectorStore: added vector id={vector_id} | '{entry['text'][:60]}'")
        return vector_id

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = VECTOR_SEARCH_TOP_K,
    ) -> list[dict]:
        """
        Find the top_k most similar vectors to the query.

        Args:
            query_embedding: float32 array of shape (EMBEDDING_DIMENSION,).
            top_k:           Maximum number of results.

        Returns:
            List of metadata dicts ordered by ascending L2 distance,
            each enriched with a 'distance' key.
            Returns an empty list if the index is empty.

        Raises:
            RuntimeError: If the index has not been initialized.
        """
        self._require_initialized()

        if self.size() == 0:
            logger.debug("VectorStore.search: index is empty — returning [].")
            return []

        self._validate_embedding(query_embedding)
        k = min(top_k, self.size())

        distances, indices = self._index.search(
            query_embedding.reshape(1, -1), k
        )

        results: list[dict] = []
        for rank, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            entry = dict(self._metadata[idx])          # copy — don't mutate stored data
            entry["distance"] = float(distances[0][rank])
            results.append(entry)

        logger.info(f"VectorStore: search returned {len(results)} results.")
        return results

    def save(self) -> None:
        """Write the FAISS index to disk."""
        self._require_initialized()
        try:
            faiss.write_index(self._index, self._index_file)
            logger.info(f"VectorStore: saved index ({self.size()} vectors) → {self._index_file}")
        except Exception as e:
            logger.exception(f"VectorStore.save failed: {e}")

    def load(self) -> None:
        """
        Load the FAISS index from disk.
        On corruption: logs the error, wipes files, and creates a fresh index.
        """
        try:
            self._index = faiss.read_index(self._index_file)
            self._metadata = self._load_metadata()
            logger.info(
                f"VectorStore: loaded existing index "
                f"({self.size()} vectors) ← {self._index_file}"
            )
        except Exception as e:
            logger.error(
                f"VectorStore: index corrupted or unreadable ({e}). "
                f"Rebuilding from scratch."
            )
            self._wipe_files()
            self._create_empty_index()

    def reset(self) -> None:
        """Wipe all vectors and metadata, then start a fresh empty index."""
        self._wipe_files()
        self._create_empty_index()
        logger.info("VectorStore: reset — all vectors cleared.")

    # ── Introspection ─────────────────────────────────────────────────────────

    def size(self) -> int:
        """Return the number of vectors currently stored."""
        return len(self._metadata)

    def is_initialized(self) -> bool:
        """Return True if the index is ready to use."""
        return self._index is not None

    # ── Private ───────────────────────────────────────────────────────────────

    def _create_empty_index(self) -> None:
        """Build a new empty L2 FAISS index and reset metadata."""
        self._index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        self._metadata = []
        self._save_metadata()

    def _require_initialized(self) -> None:
        if self._index is None:
            raise RuntimeError(
                "VectorStore has not been initialized. Call initialize() first."
            )

    def _validate_embedding(self, embedding: np.ndarray) -> None:
        if not isinstance(embedding, np.ndarray):
            raise ValueError(f"Embedding must be a numpy array, got {type(embedding)}.")
        if embedding.shape != (EMBEDDING_DIMENSION,):
            raise ValueError(
                f"Expected embedding shape ({EMBEDDING_DIMENSION},), "
                f"got {embedding.shape}."
            )

    def _ensure_directory(self) -> None:
        directory = os.path.dirname(self._index_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

    # ── Metadata I/O ──────────────────────────────────────────────────────────

    def _save_metadata(self) -> None:
        try:
            with open(self._meta_file, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.exception(f"VectorStore: failed to save metadata: {e}")

    def _load_metadata(self) -> list[dict]:
        if not os.path.exists(self._meta_file):
            logger.warning("VectorStore: metadata file missing — starting with empty metadata.")
            return []
        try:
            with open(self._meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"VectorStore: loaded {len(data)} metadata entries.")
            return data
        except Exception as e:
            logger.error(f"VectorStore: metadata unreadable ({e}) — using empty metadata.")
            return []

    def _wipe_files(self) -> None:
        for path in (self._index_file, self._meta_file):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"VectorStore: could not delete {path}: {e}")
