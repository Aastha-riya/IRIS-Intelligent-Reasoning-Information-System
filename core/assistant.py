"""
core/assistant.py

IrisAssistant — the conductor of the IRIS session.

Single responsibility:
    - Manage the user interaction loop (input / output)
    - Delegate every query to AutonomousAgent.run()
    - Speak or print the response

The assistant knows nothing about planning, tools, memory, or execution.
It only knows three things:
    1. How to get input from the user (keyboard or voice)
    2. How to pass that input to the Agent
    3. How to deliver the Agent's response back to the user

Architecture:
    main.py
        ↓
    IrisAssistant.start()
        ↓
    AutonomousAgent.run(user_input)
        ↓
    [Memory → Reason → Plan → Workflow → Executor → Reflect → Learn]
        ↓
    response (str)
        ↓
    Speaker.speak(response)
"""

from app.container import Container
from utils.logger import logger


class IrisAssistant:
    """
    Session conductor — receives input, delegates to the Agent, delivers output.
    Creates nothing. Knows nothing about internals. Just orchestrates the loop.
    """

    def __init__(self, container: Container) -> None:
        self._agent    = container.agent
        self._speaker  = container.speaker
        self._listener = container.listener

    # ── Private helpers ───────────────────────────────────────────────────────

    def _choose_mode(self) -> str:
        """Ask the user to choose keyboard or voice input."""
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
        """Capture the next user message."""
        if mode == "keyboard":
            return input("\nYou: ").strip()
        return self._listener.listen()

    def _deliver(self, response: str) -> None:
        """Print and speak the agent's response."""
        self._speaker.speak(response)

    # ── Session loop ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Start the main interaction loop.

        Flow:
            user types / speaks
                ↓
            agent.run(input)   ← entire intelligence pipeline runs here
                ↓
            speak(response)
        """
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
                self._deliver("Goodbye!")
                break

            logger.info(f"User: {user}")

            # ── Single call — everything else is the Agent's responsibility ──
            result = self._agent.run(user)

            # Produce a response even on failure
            if result.succeeded():
                response = result.output
            else:
                response = (
                    result.error
                    if result.error
                    else "I encountered an issue. Please try again."
                )

            logger.info(f"IRIS: {response[:120]}")
            self._deliver(response)
