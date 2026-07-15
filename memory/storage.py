"""
memory/storage.py

Low-level JSON file I/O — the only module that touches the filesystem.
Single responsibility: read a file, write a file, append to a file, clear a file.

Manages:
    history.json   — conversation turns
    summary.json   — compressed summaries of older conversations
    metadata.json  — session statistics and bookkeeping

No AI logic. No embeddings. No FAISS. Just storage.
"""

import json
import os

from config.settings import HISTORY_FILE, METADATA_FILE, SUMMARY_FILE
from utils.logger import logger


class Storage:
    """
    Handles reading and writing a single JSON file.
    Instantiate one Storage per file you want to manage.
    """

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._ensure_file()

    # ── Public API ────────────────────────────────────────────────────────────

    def read(self) -> list:
        """Load and return the JSON array stored at this file."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.exception(f"Storage.read failed for '{self.filepath}': {e}")
            return []

    def write(self, data: list) -> None:
        """Overwrite the file with the given data list."""
        try:
            self._write(data)
        except Exception as e:
            logger.exception(f"Storage.write failed for '{self.filepath}': {e}")

    def append(self, entry: dict) -> None:
        """Append a single dict entry to the stored list."""
        data = self.read()
        data.append(entry)
        self.write(data)
        logger.debug(f"Storage.append → {self.filepath} ({len(data)} entries)")

    def clear(self) -> None:
        """Erase all records from the file."""
        self.write([])
        logger.debug(f"Storage.clear → {self.filepath}")

    # ── Private ───────────────────────────────────────────────────────────────

    def _ensure_file(self) -> None:
        """Create the file and any missing parent directories if absent."""
        directory = os.path.dirname(self.filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.filepath):
            self._write([])
            logger.debug(f"Storage: created {self.filepath}")

    def _write(self, data: list) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


# ── Convenience factory ───────────────────────────────────────────────────────

def create_all_stores() -> dict[str, "Storage"]:
    """
    Return a dict of Storage instances for all three memory files.
    Used by MemoryManager to initialise in one call.

        stores = create_all_stores()
        stores["history"].read()
        stores["summary"].append(entry)
        stores["metadata"].write(stats)
    """
    return {
        "history":  Storage(HISTORY_FILE),
        "summary":  Storage(SUMMARY_FILE),
        "metadata": Storage(METADATA_FILE),
    }
