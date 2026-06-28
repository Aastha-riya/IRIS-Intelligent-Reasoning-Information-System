from pathlib import Path


class FileReader:

    def can_handle(self, query: str) -> bool:
        return query.lower().startswith("read ")

    def execute(self, query: str):

        filepath = query[5:].strip()

        try:
            path = Path(filepath)

            if not path.exists():
                return "File not found."

            if path.is_dir():
                return "That's a folder. Folder reading will be added next."

            with open(path, "r", encoding="utf-8") as file:
                content = file.read()

            if len(content) > 5000:
                content = content[:5000]

            return content

        except Exception as e:
            return f"Error: {e}"