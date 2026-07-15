"""
memory/embeddings.py

Embedding service — the only module that touches SentenceTransformer.

Single responsibility:
    text string  →  384-dimensional float32 vector

Nothing else.  No FAISS.  No JSON.  No retrieval.  No LLM.  Just embeddings.

Model: sentence-transformers/all-MiniLM-L6-v2
    - Fast and small (~80 MB)
    - 384-dimensional output
    - Excellent accuracy for semantic similarity
    - Works fully offline
    - Industry standard — easy to explain in interviews

Caching:
    Repeated sentences are looked up in a plain dict before calling the model.
    This avoids redundant inference for common phrases like greetings.
    Cache lives in memory only — it resets each session (intentional for now).

Error handling:
    Empty strings      → raises ValueError with a clear message
    Very long text     → silently truncated to MAX_EMBED_CHARS before encoding
    Model load failure → raises RuntimeError so the application fails fast at startup
    Encode failure     → raises RuntimeError with context for the caller to handle
"""

import numpy as np
from sentence_transformers import SentenceTransformer

from config.settings import EMBEDDING_MODEL, EMBEDDING_DIMENSION
from utils.logger import logger

# Maximum characters accepted per encode call.
# all-MiniLM-L6-v2 has a 256-token limit; ~1 500 chars is a safe ceiling.
MAX_EMBED_CHARS: int = 1_500


class EmbeddingService:
    """
    Converts text into fixed-size float32 vectors using all-MiniLM-L6-v2.

    Usage:
        service = EmbeddingService()
        vector  = service.generate_embedding("My favourite editor is VS Code.")
        # → numpy array, shape (384,), dtype float32

    One instance should be created in the Container and shared everywhere.
    If you switch models later, only this file changes.
    """

    def __init__(self) -> None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL} ...")
        try:
            self._model = SentenceTransformer(EMBEDDING_MODEL)
        except Exception as e:
            logger.exception(f"Failed to load embedding model '{EMBEDDING_MODEL}': {e}")
            raise RuntimeError(
                f"Embedding model '{EMBEDDING_MODEL}' could not be loaded. "
                f"Install it with: pip install sentence-transformers"
            ) from e

        self.dimension: int = EMBEDDING_DIMENSION
        self._cache: dict[str, np.ndarray] = {}   # text → vector

        logger.info(f"Embedding service ready — dimension: {self.dimension}")

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Encode a single string into a 1-D float32 numpy array of shape (384,).

        Args:
            text: The sentence or paragraph to embed.

        Returns:
            float32 numpy array of shape (dimension,).

        Raises:
            ValueError:   If text is empty or whitespace-only.
            RuntimeError: If the model fails to produce an embedding.
        """
        text = self._validate_and_prepare(text)

        # Cache hit — no inference needed
        if text in self._cache:
            logger.debug("EmbeddingService: cache hit.")
            return self._cache[text]

        # Cache miss — run the model
        try:
            vector = self._model.encode([text], convert_to_numpy=True)
            result = vector[0].astype("float32")
        except Exception as e:
            logger.exception(f"EmbeddingService.generate_embedding failed: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

        self._cache[text] = result
        logger.debug(f"EmbeddingService: encoded and cached (cache size: {len(self._cache)}).")
        return result

    def generate_batch(self, texts: list[str]) -> np.ndarray:
        """
        Encode a list of strings into a 2-D float32 numpy array of shape (N, 384).
        Each text is individually validated and truncated before batching.

        Args:
            texts: List of strings to embed.

        Returns:
            float32 numpy array of shape (len(texts), dimension).

        Raises:
            ValueError:   If the list is empty.
            RuntimeError: If the model fails.
        """
        if not texts:
            raise ValueError("generate_batch requires at least one text.")

        prepared = [self._validate_and_prepare(t) for t in texts]

        try:
            vectors = self._model.encode(prepared, convert_to_numpy=True)
            result = vectors.astype("float32")
        except Exception as e:
            logger.exception(f"EmbeddingService.generate_batch failed: {e}")
            raise RuntimeError(f"Batch embedding failed: {e}") from e

        # Cache each result individually for future single lookups
        for text, vector in zip(prepared, result):
            self._cache[text] = vector

        logger.debug(f"EmbeddingService: batch of {len(prepared)} encoded.")
        return result

    def cache_size(self) -> int:
        """Return the number of cached embeddings."""
        return len(self._cache)

    def clear_cache(self) -> None:
        """Evict all cached embeddings."""
        self._cache.clear()
        logger.debug("EmbeddingService: cache cleared.")

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_and_prepare(text: str) -> str:
        """
        Validate and sanitize a text input before encoding.

        - Raises ValueError for empty / whitespace-only input.
        - Silently truncates to MAX_EMBED_CHARS if the text is too long.

        Returns the cleaned, possibly truncated string.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                "EmbeddingService requires a non-empty string. "
                f"Received: {repr(text)}"
            )

        text = text.strip()

        if len(text) > MAX_EMBED_CHARS:
            logger.warning(
                f"EmbeddingService: input truncated from {len(text)} "
                f"to {MAX_EMBED_CHARS} characters."
            )
            text = text[:MAX_EMBED_CHARS]

        return text
