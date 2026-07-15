"""
voice/listen.py

Microphone-based speech recognition using SpeechRecognition + Google STT.
Returns transcribed text or an empty string on failure.
"""

import speech_recognition as sr

from config.settings import AMBIENT_NOISE_DURATION
from utils.logger import logger


class Listener:
    """Captures audio from the microphone and transcribes it to text."""

    def __init__(self) -> None:
        self.recognizer = sr.Recognizer()
        logger.debug("Listener initialized.")

    def listen(self) -> str:
        """
        Record a spoken utterance and return the transcribed text.
        Returns an empty string if recognition fails.
        """
        print("🎤 Listening...")   # UI feedback — intentional print()
        logger.debug("Listening for audio input...")

        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(
                    source, duration=AMBIENT_NOISE_DURATION
                )
                audio = self.recognizer.listen(source)

            text: str = self.recognizer.recognize_google(audio)
            logger.info(f"User (voice): {text}")
            return text

        except sr.UnknownValueError:
            logger.warning("Could not understand audio.")
            return ""

        except sr.RequestError as e:
            logger.error(f"Speech recognition service unavailable: {e}")
            return ""

        except Exception as e:
            logger.exception(f"Listener failed unexpectedly: {e}")
            return ""
