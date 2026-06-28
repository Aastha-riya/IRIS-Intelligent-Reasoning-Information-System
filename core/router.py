from brain.reasoner import Reasoner
from tools.tool_manager import ToolManager


class Router:

    def __init__(self):
        self.reasoner = Reasoner()
        self.tools = ToolManager()

    def process(self, query):

        action = self.reasoner.analyze(query)

        if action == "llm":
            return query, False

        result = self.tools.execute(query)

        return result, True