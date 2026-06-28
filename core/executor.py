class Executor:

    def execute(self, plan):

        print("\nExecution Plan\n")

        for step in plan["steps"]:
            step["status"] = "completed"
            print(f"✓ {step['description']}")

        print()

        return plan