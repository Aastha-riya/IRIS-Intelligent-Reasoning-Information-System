"""
tools/file_reader.py

Reads the contents of a file path provided in the user query.
"""

from pathlib import Path

from config.settings import MAX_FILE_READ_CHARS
from utils.logger import logger


class FileReader:
    """Reads and returns the text content of a file specified in the query."""

    def can_handle(self, query: str) -> bool:
        """Return True if the query starts with 'read '."""
        return query.lower().startswith("read ")

    def execute(self, query: str) -> str:
        """
        Parse the file path from the query, read its content, and return it.
        Content is truncated to MAX_FILE_READ_CHARS characters.
        """
        filepath = query[5:].strip()
        logger.info(f"FileReader reading: {filepath}")

        try:
            path = Path(filepath)

            if not path.exists():
                logger.warning(f"File not found: {filepath}")
                return "File not found."

            if path.is_dir():
                logger.warning(f"Path is a directory: {filepath}")
                return "That's a folder. Use 'scan' to inspect a project directory."

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if len(content) > MAX_FILE_READ_CHARS:
                logger.debug(f"File truncated to {MAX_FILE_READ_CHARS} characters.")
                content = content[:MAX_FILE_READ_CHARS]

            logger.info(f"FileReader successfully read: {filepath}")
            return content

        except Exception as e:
            logger.exception(f"FileReader failed for '{filepath}': {e}")
            return f"Error reading file: {e}"
