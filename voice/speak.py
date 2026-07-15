"""
voice/speak.py

Text-to-speech output using pyttsx3.
Prints the response to the terminal as UI feedback in addition to speaking it.
"""

import pyttsx3

from config.settings import VOICE_SPEED
from utils.logger import logger


class Speaker:
    """Converts text to speech and outputs it through the system audio."""

    def __init__(self) -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", VOICE_SPEED)
        logger.debug(f"Speaker initialized at {VOICE_SPEED} wpm.")

    def speak(self, text: str) -> None:
        """Speak the given text aloud and print it to the terminal."""
        self.engine.stop()
        print(f"IRIS: {text}")   # UI output — intentional print()
        logger.debug(f"Speaking: {text[:80]}{'...' if len(text) > 80 else ''}")
        self.engine.say(text)
        self.engine.runAndWait()

    def stop(self) -> None:
        """Stop any speech currently in progress."""
        self.engine.stop()
        logger.debug("Speaker stopped.")
