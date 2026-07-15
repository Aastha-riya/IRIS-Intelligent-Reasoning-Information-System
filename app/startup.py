from config.settings import ASSISTANT_NAME
from app.container import Container
from utils.logger import logger


class Startup:
    """
    Responsible for bootstrapping the application.
    Loads settings, builds the container, returns it.
    No AI logic. No chat loops. No tool execution.
    """

    @staticmethod
    def initialize() -> Container:
        logger.info(f"Starting {ASSISTANT_NAME}...")

        container = Container()

        logger.info("All systems initialized.")
        return container
