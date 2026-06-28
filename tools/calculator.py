from tools.base_tool import BaseTool


class Calculator(BaseTool):

    name = "calculator"

    description = "Solve mathematical expressions."

    def can_handle(self, query):

        keywords = [
            "calculate",
            "+",
            "-",
            "*",
            "/"
        ]

        return any(word in query.lower() for word in keywords)

    def execute(self, query):

        expression = query.lower().replace("calculate", "").strip()

        try:
            return eval(expression)

        except:
            return "Invalid expression."