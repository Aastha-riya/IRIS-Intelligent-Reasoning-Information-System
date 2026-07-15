"""
core/assistant.py

Orchestrates the IRIS session loop.
Receives all dependencies via the Container — creates nothing itself.
"""

from app.container import Container
from utils.logger import logger


class IrisAssistant:
    """
    Main session controller.
    Handles user input, routes to tools or LLM, and speaks replies.
    All memory operations go through memory_manager — never directly to storage.
    """

    def __init__(self, container: Container) -> None:
        self.llm            = container.llm
        self.memory_manager = container.memory_manager
        self.speaker        = container.speaker
        self.listener       = container.listener
        self.tool_manager   = container.tool_manager
        self.reasoner       = container.reasoner
        self.planner        = container.planner
        self.executor       = container.executor

    # ── Private helpers ───────────────────────────────────────────────────────

    def _choose_mode(self) -> str:
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

    def _get_input(self, mode: str) -> str:
        if mode == "keyboard":
            return input("\nYou: ").strip()
        return self.listener.listen()

    # ── Session loop ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the main interaction loop."""
        mode = self._choose_mode()
        logger.info(f"Session started in {mode} mode.")

        print("\n🤖 IRIS is Online!")
        print("Type 'exit' anytime to quit.\n")

        while True:
            user = self._get_input(mode)

            if not user:
                continue

            if user.lower() in ["exit", "quit", "bye"]:
                logger.info("Session ended by user.")
                self.speaker.speak("Goodbye!")
                break

            logger.info(f"User: {user}")

            # Route: tool or LLM?
            action = self.reasoner.analyze(user)
            logger.debug(f"Reasoner decision: {action}")

            if action != "llm":
                result = self.tool_manager.execute(user)
                if result:
                    self.speaker.speak(result)
                    continue

            # Plan → execute → LLM reply
            plan = self.planner.create_plan(user)
            self.executor.execute(plan)

            reply = self.llm.chat(user)
            self.speaker.speak(reply)
