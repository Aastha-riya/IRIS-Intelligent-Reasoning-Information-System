class Reasoner:

    def analyze(self, query: str):

        query = query.lower()

        if any(op in query for op in ["+", "-", "*", "/", "calculate"]):
            return "calculator"

        elif query.startswith("read "):
            return "file_reader"

        elif query.startswith("scan "):
            return "project_scanner"

        elif query.startswith("search "):
            return "internet"

        else:
            return "llm"