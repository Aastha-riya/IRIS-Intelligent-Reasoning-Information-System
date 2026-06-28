from tools.calculator import Calculator
#from tools.internet import Internet
from tools.file_reader import FileReader
from tools.project_scanner import ProjectScanner


class ToolManager:

    def __init__(self):

        self.tools = {
            "calculator": Calculator(),
            "file_reader": FileReader(),
             "project_scanner": ProjectScanner()

        }

    def execute(self, query):

        for tool in self.tools:

            if tool.can_handle(query):
                return tool.execute(query)

        return None