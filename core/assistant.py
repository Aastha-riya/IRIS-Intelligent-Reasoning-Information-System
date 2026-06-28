from brain.llm import LLM
from voice.speak import Speaker
from voice.listen import Listener
from tools.tool_manager import ToolManager
from core.router import Router
from brain.planner import Planner
from core.executor import Executor

class IrisAssistant:

    def __init__(self):
        self.brain = LLM()
        self.speaker = Speaker()
        self.listener = Listener()
        self.tools = ToolManager()
        self.router = Router()
        self.planner = Planner()
        self.executor = Executor()

    def choose_mode(self):
        print("\n========== IRIS ==========")
        print("1. Keyboard Mode")
        print("2. Voice Mode")
        print("==========================")

        while True:
            choice = input("Choose mode (1/2): ").strip()

            if choice == "1":
                return "keyboard"

            elif choice == "2":
                return "voice"

            print("Invalid choice. Please enter 1 or 2.")

    def get_input(self, mode):
        if mode == "keyboard":
            return input("\nYou: ").strip()

        return self.listener.listen()

    def run(self):
        mode = self.choose_mode()

        print("\n🤖 IRIS is Online!")
        print("Type 'exit' anytime to quit.\n")

        while True:

            user = self.get_input(mode)

            if not user:
                continue

            if user.lower() in ["exit", "quit", "bye"]:
                self.speaker.speak("Goodbye!")
                break

            tool_result = self.tools.execute(user)

            if tool_result:
                self.speaker.speak(tool_result)
                continue

            processed, handled = self.router.process(user)

            if handled:
                self.speaker.speak(str(processed))
                continue

            plan = self.planner.create_plan(user)
            self.executor.execute(plan)


            reply = self.brain.chat(user)

            self.speaker.speak(reply)