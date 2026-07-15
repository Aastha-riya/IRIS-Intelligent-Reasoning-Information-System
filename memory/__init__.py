"""
memory package

Public surface — the rest of the application imports only MemoryManager.
All internal modules are implementation details.

Internal structure:
    storage.py        — JSON file I/O
    history.py        — conversation turn model
    embeddings.py     — SentenceTransformer wrapper
    vector_store.py   — FAISS index wrapper
    retriever.py      — semantic search (embeddings → FAISS → results)
    context_builder.py — RAG prompt assembly
    summarizer.py     — history compression (stub)
    memory_manager.py — coordinates all of the above
"""

from memory.memory_manager import MemoryManager

__all__ = ["MemoryManager"]
