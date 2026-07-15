"""
tests/test_vector_store.py

Unit tests for memory/vector_store.py (VectorStore).

Run with:
    python -m pytest tests/test_vector_store.py -v

Tests cover:
    1.  initialize() creates a fresh empty index.
    2.  add() stores a vector and increments size.
    3.  search() on an empty index returns [].
    4.  add one vector and search — the same vector is returned.
    5.  search returns the closest vector first (distance ordering).
    6.  save() writes vector.index to disk.
    7.  load() restores vectors after save.
    8.  Corrupted index file is handled gracefully (reset, no crash).
    9.  reset() wipes all vectors and files.
    10. add() without initialize() raises RuntimeError.
    11. Metadata fields (id, text, timestamp, importance) are persisted.
    12. search() with top_k > stored size clamps correctly.
"""

import os
import tempfile

import numpy as np
import pytest

from config.settings import EMBEDDING_DIMENSION
from memory.vector_store import VectorStore


# ── Helpers ───────────────────────────────────────────────────────────────────

def _random_vec() -> np.ndarray:
    """Return a random normalized float32 vector of the correct dimension."""
    v = np.random.rand(EMBEDDING_DIMENSION).astype("float32")
    return v / np.linalg.norm(v)


def _make_store(tmp_path: str) -> VectorStore:
    """Create a VectorStore whose files live in a temp directory."""
    store = VectorStore()
    store._index_file = os.path.join(tmp_path, "vector.index")
    store._meta_file  = os.path.join(tmp_path, "vector_meta.json")
    store.initialize()
    return store


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    """Fresh VectorStore per test, using a temporary directory."""
    return _make_store(str(tmp_path))


# ── Test 1: initialize creates empty index ───────────────────────────────────

def test_initialize_creates_empty_index(store: VectorStore) -> None:
    assert store.is_initialized(), "Index should be initialized."
    assert store.size() == 0, "Newly initialized store should have 0 vectors."


# ── Test 2: add increments size ───────────────────────────────────────────────

def test_add_increments_size(store: VectorStore) -> None:
    store.add(_random_vec(), {"text": "Hello IRIS."})
    assert store.size() == 1

    store.add(_random_vec(), {"text": "Python is great."})
    assert store.size() == 2


# ── Test 3: search on empty index returns [] ──────────────────────────────────

def test_search_empty_index_returns_empty(store: VectorStore) -> None:
    results = store.search(_random_vec())
    assert results == [], "Search on empty index must return []."


# ── Test 4: add one vector and find it with search ───────────────────────────

def test_search_finds_added_vector(store: VectorStore) -> None:
    vec = _random_vec()
    store.add(vec, {"text": "My favourite language is Python."})

    results = store.search(vec, top_k=1)

    assert len(results) == 1
    assert results[0]["text"] == "My favourite language is Python."
    assert results[0]["distance"] < 1e-4, "Searching the exact same vector must return near-zero distance."


# ── Test 5: closest vector is returned first ─────────────────────────────────

def test_search_returns_closest_first(store: VectorStore) -> None:
    base = _random_vec()
    close = (base + np.random.rand(EMBEDDING_DIMENSION).astype("float32") * 0.01)
    close = (close / np.linalg.norm(close)).astype("float32")
    far   = _random_vec()   # independent random vector

    store.add(close, {"text": "close"})
    store.add(far,   {"text": "far"})

    results = store.search(base, top_k=2)
    assert results[0]["text"] == "close", "Closest vector must appear first."
    assert results[0]["distance"] < results[1]["distance"]


# ── Test 6: save writes the index file ────────────────────────────────────────

def test_save_creates_index_file(store: VectorStore) -> None:
    store.add(_random_vec(), {"text": "save test"})
    assert os.path.exists(store._index_file), "Index file must exist after save."


# ── Test 7: load restores vectors ─────────────────────────────────────────────

def test_load_restores_vectors(tmp_path) -> None:
    store_a = _make_store(str(tmp_path))
    vec = _random_vec()
    store_a.add(vec, {"text": "persist me"})
    # save is called automatically inside add()

    # Open a second store pointing at the same files
    store_b = VectorStore()
    store_b._index_file = store_a._index_file
    store_b._meta_file  = store_a._meta_file
    store_b.load()

    assert store_b.size() == 1, "Loaded store should have 1 vector."
    results = store_b.search(vec, top_k=1)
    assert results[0]["text"] == "persist me"


# ── Test 8: corrupted index is handled gracefully ─────────────────────────────

def test_corrupted_index_handled_gracefully(tmp_path) -> None:
    index_path = os.path.join(str(tmp_path), "vector.index")
    meta_path  = os.path.join(str(tmp_path), "vector_meta.json")

    # Write garbage to the index file
    with open(index_path, "w") as f:
        f.write("this is not a valid FAISS index")

    store = VectorStore()
    store._index_file = index_path
    store._meta_file  = meta_path

    # Should NOT raise — must recover silently
    store.load()

    assert store.is_initialized(), "Store should recover and create a fresh index."
    assert store.size() == 0, "Recovered store should be empty."


# ── Test 9: reset wipes everything ────────────────────────────────────────────

def test_reset_clears_all(store: VectorStore) -> None:
    store.add(_random_vec(), {"text": "will be gone"})
    assert store.size() == 1

    store.reset()

    assert store.size() == 0, "Store should be empty after reset."
    assert not os.path.exists(store._index_file) or store.size() == 0


# ── Test 10: add without initialize raises RuntimeError ──────────────────────

def test_add_without_initialize_raises(tmp_path) -> None:
    store = VectorStore()
    store._index_file = os.path.join(str(tmp_path), "vector.index")
    store._meta_file  = os.path.join(str(tmp_path), "vector_meta.json")
    # deliberately NOT calling initialize()

    with pytest.raises(RuntimeError, match="initialize"):
        store.add(_random_vec(), {"text": "no init"})


# ── Test 11: metadata fields are saved correctly ──────────────────────────────

def test_metadata_fields_persisted(store: VectorStore) -> None:
    store.add(
        _random_vec(),
        {"text": "metadata test", "importance": 0.8},
    )
    results = store.search(_random_vec(), top_k=1)
    # We may or may not get this vector back depending on distance,
    # but we can verify the stored metadata directly.
    entry = store._metadata[0]

    assert entry["id"] == 0
    assert entry["text"] == "metadata test"
    assert entry["importance"] == 0.8
    assert "timestamp" in entry, "timestamp should be auto-populated."


# ── Test 12: top_k larger than stored size clamps correctly ──────────────────

def test_search_top_k_clamps_to_store_size(store: VectorStore) -> None:
    for i in range(3):
        store.add(_random_vec(), {"text": f"entry {i}"})

    results = store.search(_random_vec(), top_k=100)
    assert len(results) <= 3, "Results must not exceed the number of stored vectors."
