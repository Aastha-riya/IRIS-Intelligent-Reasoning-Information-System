class Planner:

    def create_plan(self, task: str):

        return {
            "goal": task,
            "steps": [
                {
                    "id": 1,
                    "description": "Understand the user's request",
                    "status": "pending"
                },
                {
                    "id": 2,
                    "description": "Choose the correct tool",
                    "status": "pending"
                },
                {
                    "id": 3,
                    "description": "Execute the task",
                    "status": "pending"
                },
                {
                    "id": 4,
                    "description": "Generate the response",
                    "status": "pending"
                }
            ]
        }