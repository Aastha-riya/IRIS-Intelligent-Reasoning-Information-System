"""
app/startup.py

Bootstraps the IRIS application.
Loads settings, builds the Container, returns it.
No AI logic. No chat loops. No tool execution.
"""

from config.settings import ASSISTANT_NAME
from app.container import Container
from utils.logger import logger


class Startup:
    """Single responsibility: initialise the Container and return it."""

    @staticmethod
    def initialize() -> Container:
        logger.info(f"Starting {ASSISTANT_NAME}...")
        logger.info("Pipeline: Memory → Agent → Workflow → Executor → Reflection → LLM")

        container = Container()

        logger.info("=" * 56)
        logger.info(f"  {ASSISTANT_NAME} — Intelligent Reasoning Information System")
        logger.info("  All systems initialised and ready.")
        logger.info("=" * 56)

        return container
