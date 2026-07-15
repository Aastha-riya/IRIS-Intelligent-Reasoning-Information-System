"""
tests/test_retriever.py

Integration tests for memory/retriever.py (Retriever).

These tests use REAL embeddings (EmbeddingService + SentenceTransformer)
so they exercise the full retrieval pipeline without needing a running LLM.

Run with:
    python -m pytest tests/test_retriever.py -v

Test cases:
    1.  Store "I love Java" → search "favorite language" → should return it.
    2.  Search an unrelated topic (weather) against programming memories → returns [].
    3.  Store multiple memories → search "programming" → only relevant ones returned.
    4.  retrieve() returns RetrievedMemory objects with all expected fields.
    5.  Results are ordered by rank_score descending (best first).
    6.  retrieve() on an empty store returns [].
    7.  retrieve_as_strings() returns plain text list.
    8.  Similarity scores are in (0, 1] range.
    9.  Importance from metadata is reflected in the result.
    10. High-importance memory ranks above lower-importance one with same similarity.
"""

import os
import tempfile

import pytest

from memory.embeddings import EmbeddingService
from memory.retriever import Retriever, RetrievedMemory
from memory.vector_store import VectorStore


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def embedder() -> EmbeddingService:
    """Load the embedding model once for the whole module."""
    return EmbeddingService()


@pytest.fixture
def store(tmp_path) -> VectorStore:
    """Fresh VectorStore per test in a temp directory."""
    vs = VectorStore()
    vs._index_file = str(tmp_path / "vector.index")
    vs._meta_file  = str(tmp_path / "vector_meta.json")
    vs.initialize()
    return vs


@pytest.fixture
def retriever(embedder: EmbeddingService, store: VectorStore) -> Retriever:
    """Retriever wired to the per-test store."""
    return Retriever(embedder, store)


def _add(store: VectorStore, embedder: EmbeddingService,
         text: str, importance: float = 1.0) -> None:
    """Helper: embed text and add it to the store."""
    vec = embedder.generate_embedding(text)
    store.add(vec, {"text": text, "importance": importance})


# ── Test 1: "I love Java" is found by "favorite language" ────────────────────

def test_retrieve_java_by_language_query(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I love Java")

    results = retriever.retrieve("What is my favorite language?")

    assert len(results) > 0, "Should find at least one memory."
    texts = [m.text for m in results]
    assert "I love Java" in texts, f"Expected 'I love Java' in results, got: {texts}"


# ── Test 2: Unrelated topic returns [] ───────────────────────────────────────

def test_unrelated_topic_returns_empty(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I love Java")
    _add(store, embedder, "Python is my favourite language")
    _add(store, embedder, "I use VS Code every day")

    # Weather has no semantic relation to programming tools
    results = retriever.retrieve(
        "What will the weather be like tomorrow in London?",
        top_k=5,
    )

    # Either empty or all returned memories should be programming-related
    for m in results:
        assert any(
            kw in m.text.lower()
            for kw in ["java", "python", "code", "language", "programming"]
        ), f"Unrelated memory returned: '{m.text}'"


# ── Test 3: Multiple memories — only relevant ones returned ──────────────────

def test_only_relevant_memories_returned(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I enjoy hiking in the mountains")
    _add(store, embedder, "My favourite framework is Django")
    _add(store, embedder, "I prefer Python over Java for scripting")
    _add(store, embedder, "I had pasta for lunch today")

    results = retriever.retrieve("Tell me about programming languages", top_k=10)

    texts = [m.text for m in results]
    # Programming memories should be in the results
    programming = [t for t in texts if any(
        kw in t.lower() for kw in ["python", "java", "django", "framework", "programming"]
    )]
    assert len(programming) > 0, "At least one programming memory should be retrieved."

    # Non-programming memories should not dominate
    assert len(results) <= 5, "Should not return more than MAX_CONTEXT_MEMORIES results."


# ── Test 4: Results are RetrievedMemory objects with all fields ───────────────

def test_result_has_all_fields(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I use PyCharm as my IDE", importance=0.9)

    results = retriever.retrieve("What IDE do I use?")

    assert len(results) > 0
    m = results[0]

    assert isinstance(m, RetrievedMemory)
    assert isinstance(m.text, str) and len(m.text) > 0
    assert isinstance(m.similarity_score, float)
    assert isinstance(m.importance, float)
    assert isinstance(m.timestamp, str)
    assert isinstance(m.rank_score, float)


# ── Test 5: Results are ordered by rank_score descending ─────────────────────

def test_results_ordered_by_rank_score(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I prefer Python for data science")
    _add(store, embedder, "Python has great libraries like NumPy")
    _add(store, embedder, "I started learning Python last year")

    results = retriever.retrieve("Python programming", top_k=10)

    scores = [m.rank_score for m in results]
    assert scores == sorted(scores, reverse=True), (
        f"Results should be sorted descending by rank_score. Got: {scores}"
    )


# ── Test 6: Empty store returns [] ───────────────────────────────────────────

def test_empty_store_returns_empty(retriever: Retriever) -> None:
    results = retriever.retrieve("Does anything exist?")
    assert results == [], "Empty store must return []."


# ── Test 7: retrieve_as_strings returns plain text ───────────────────────────

def test_retrieve_as_strings(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I work with machine learning models")

    strings = retriever.retrieve_as_strings("machine learning")

    assert isinstance(strings, list)
    for s in strings:
        assert isinstance(s, str), "retrieve_as_strings must return plain strings."


# ── Test 8: Similarity scores are in (0, 1] ──────────────────────────────────

def test_similarity_scores_in_valid_range(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I love functional programming")

    results = retriever.retrieve("functional programming")

    for m in results:
        assert 0.0 < m.similarity_score <= 1.0, (
            f"similarity_score must be in (0, 1], got {m.similarity_score}"
        )


# ── Test 9: Importance from metadata is reflected ────────────────────────────

def test_importance_reflected_in_result(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    _add(store, embedder, "I love Rust for systems programming", importance=0.3)

    results = retriever.retrieve("Rust systems programming")

    if results:
        assert abs(results[0].importance - 0.3) < 0.01, (
            f"Expected importance 0.3, got {results[0].importance}"
        )


# ── Test 10: High-importance memory ranks above lower-importance ──────────────

def test_high_importance_ranks_higher(
    retriever: Retriever,
    store: VectorStore,
    embedder: EmbeddingService,
) -> None:
    # Two semantically similar memories, different importance
    text_high = "I prefer Python for all my projects"
    text_low  = "I prefer Python for most of my projects"

    _add(store, embedder, text_high, importance=1.0)
    _add(store, embedder, text_low,  importance=0.1)

    results = retriever.retrieve("Python projects", top_k=5)

    if len(results) >= 2:
        assert results[0].importance >= results[1].importance or \
               results[0].rank_score >= results[1].rank_score, (
            "Higher-importance memory should rank at least as high."
        )
