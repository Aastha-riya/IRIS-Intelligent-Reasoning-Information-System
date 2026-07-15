"""
tools/project_scanner.py

Scans a project directory and lists source files by extension.
Ignores common non-source folders (venv, git, cache, etc.).
"""

from pathlib import Path

from utils.logger import logger


class ProjectScanner:
    """Scans a project folder and reports all relevant source files."""

    IGNORE: frozenset = frozenset({
        ".git", ".idea", ".venv",
        "__pycache__", "node_modules",
        "target", "build",
    })

    EXTENSIONS: frozenset = frozenset({
        ".py", ".java", ".html", ".css",
        ".js", ".jsp", ".xml", ".md",
    })

    MAX_FILES_REPORTED: int = 100

    def can_handle(self, query: str) -> bool:
        """Return True if the query starts with 'scan '."""
        return query.lower().startswith("scan ")

    def execute(self, query: str) -> str:
        """
        Scan the folder specified in the query and return a
        formatted report of source files found.
        """
        folder = Path(query[5:].strip())
        logger.info(f"ProjectScanner scanning: {folder}")

        if not folder.exists():
            logger.warning(f"Folder not found: {folder}")
            return "Folder not found."

        try:
            files: list[str] = [
                str(file)
                for file in folder.rglob("*")
                if not any(part in self.IGNORE for part in file.parts)
                and file.suffix.lower() in self.EXTENSIONS
            ]

            logger.info(f"ProjectScanner found {len(files)} files in '{folder}'.")

            report = [
                f"Project: {folder.name}",
                f"Files Found: {len(files)}",
                "",
                "Files:",
                *files[:self.MAX_FILES_REPORTED],
            ]
            return "\n".join(report)

        except Exception as e:
            logger.exception(f"ProjectScanner failed for '{folder}': {e}")
            return f"Scan error: {e}"
