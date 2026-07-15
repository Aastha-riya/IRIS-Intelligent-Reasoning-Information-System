"""
tests/test_embeddings.py

Unit tests for memory/embeddings.py (EmbeddingService).

Run with:
    python -m pytest tests/test_embeddings.py -v

Tests cover:
    1.  Normal input produces a valid numpy vector of the correct shape/dtype.
    2.  Same sentence twice produces identical embeddings (determinism).
    3.  Different sentences produce different embeddings (discriminability).
    4.  Empty string raises ValueError.
    5.  Whitespace-only string raises ValueError.
    6.  Non-string input raises ValueError.
    7.  Very long text is truncated without crashing.
    8.  Cache hit returns the same object without re-encoding.
    9.  Cache size grows as expected.
    10. clear_cache() resets the cache.
    11. generate_batch() returns correct shape.
    12. generate_batch() with empty list raises ValueError.
"""

import numpy as np
import pytest

from memory.embeddings import EmbeddingService, MAX_EMBED_CHARS
from config.settings import EMBEDDING_DIMENSION


# ── Fixture — one service instance shared across all tests ────────────────────

@pytest.fixture(scope="module")
def service() -> EmbeddingService:
    """Load the model once for the whole test module."""
    return EmbeddingService()


# ── Test 1: Normal output shape and dtype ─────────────────────────────────────

def test_generate_embedding_returns_correct_shape(service: EmbeddingService) -> None:
    vector = service.generate_embedding("Hello, my name is IRIS.")
    assert isinstance(vector, np.ndarray), "Output should be a numpy array."
    assert vector.shape == (EMBEDDING_DIMENSION,), (
        f"Expected shape ({EMBEDDING_DIMENSION},), got {vector.shape}."
    )
    assert vector.dtype == np.float32, f"Expected float32, got {vector.dtype}."


# ── Test 2: Determinism — same input, same output ─────────────────────────────

def test_same_sentence_produces_identical_embeddings(service: EmbeddingService) -> None:
    sentence = "My favourite programming language is Python."
    v1 = service.generate_embedding(sentence)
    v2 = service.generate_embedding(sentence)
    np.testing.assert_array_equal(v1, v2, err_msg="Same sentence must yield identical vectors.")


# ── Test 3: Different sentences produce different vectors ─────────────────────

def test_different_sentences_produce_different_embeddings(service: EmbeddingService) -> None:
    v1 = service.generate_embedding("I love Python.")
    v2 = service.generate_embedding("The sky is blue.")
    assert not np.array_equal(v1, v2), "Different sentences must yield different vectors."


# ── Test 4: Empty string raises ValueError ────────────────────────────────────

def test_empty_string_raises_value_error(service: EmbeddingService) -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        service.generate_embedding("")


# ── Test 5: Whitespace-only string raises ValueError ─────────────────────────

def test_whitespace_only_raises_value_error(service: EmbeddingService) -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        service.generate_embedding("   ")


# ── Test 6: Non-string input raises ValueError ────────────────────────────────

def test_non_string_input_raises_value_error(service: EmbeddingService) -> None:
    with pytest.raises(ValueError):
        service.generate_embedding(None)   # type: ignore[arg-type]

    with pytest.raises(ValueError):
        service.generate_embedding(12345)  # type: ignore[arg-type]


# ── Test 7: Very long text is truncated without crashing ─────────────────────

def test_very_long_text_is_handled(service: EmbeddingService) -> None:
    long_text = "word " * 2000     # ~10 000 characters — well above MAX_EMBED_CHARS
    vector = service.generate_embedding(long_text)
    assert vector.shape == (EMBEDDING_DIMENSION,), "Long text should still return a valid vector."


# ── Test 8: Cache hit returns the same array object ──────────────────────────

def test_cache_returns_same_object(service: EmbeddingService) -> None:
    service.clear_cache()
    sentence = "Cache test sentence."
    v1 = service.generate_embedding(sentence)
    v2 = service.generate_embedding(sentence)     # should be a cache hit
    assert v1 is v2, "Cache hit should return the exact same numpy object."


# ── Test 9: Cache size grows correctly ───────────────────────────────────────

def test_cache_size_grows(service: EmbeddingService) -> None:
    service.clear_cache()
    assert service.cache_size() == 0

    service.generate_embedding("First unique sentence.")
    assert service.cache_size() == 1

    service.generate_embedding("Second unique sentence.")
    assert service.cache_size() == 2

    # Repeated sentence should not grow the cache
    service.generate_embedding("First unique sentence.")
    assert service.cache_size() == 2


# ── Test 10: clear_cache resets the cache ────────────────────────────────────

def test_clear_cache(service: EmbeddingService) -> None:
    service.generate_embedding("Something to cache.")
    assert service.cache_size() > 0

    service.clear_cache()
    assert service.cache_size() == 0, "Cache should be empty after clear_cache()."


# ── Test 11: generate_batch returns correct shape ────────────────────────────

def test_generate_batch_correct_shape(service: EmbeddingService) -> None:
    texts = ["First sentence.", "Second sentence.", "Third sentence."]
    matrix = service.generate_batch(texts)
    assert matrix.shape == (3, EMBEDDING_DIMENSION), (
        f"Expected shape (3, {EMBEDDING_DIMENSION}), got {matrix.shape}."
    )
    assert matrix.dtype == np.float32


# ── Test 12: generate_batch with empty list raises ValueError ────────────────

def test_generate_batch_empty_list_raises(service: EmbeddingService) -> None:
    with pytest.raises(ValueError):
        service.generate_batch([])
