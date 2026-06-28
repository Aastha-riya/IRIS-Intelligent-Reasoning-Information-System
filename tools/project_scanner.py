from pathlib import Path


class ProjectScanner:

    IGNORE = {
        ".git",
        ".idea",
        ".venv",
        "__pycache__",
        "node_modules",
        "target",
        "build"
    }

    EXTENSIONS = {
        ".py",
        ".java",
        ".html",
        ".css",
        ".js",
        ".jsp",
        ".xml",
        ".md"
    }

    def can_handle(self, query):
        return query.lower().startswith("scan ")

    def execute(self, query):

        folder = Path(query[5:].strip())

        if not folder.exists():
            return "Folder not found."

        files = []

        for file in folder.rglob("*"):

            if any(part in self.IGNORE for part in file.parts):
                continue

            if file.suffix.lower() in self.EXTENSIONS:
                files.append(str(file))

        report = [
            f"Project: {folder.name}",
            f"Files Found: {len(files)}",
            "",
            "Files:"
        ]

        report.extend(files[:100])

        return "\n".join(report)