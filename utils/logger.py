"""
utils/logger.py

Configures the application-wide logger for IRIS.
Import this module's `logger` instance everywhere — never configure
logging separately in individual modules.

Usage:
    from utils.logger import logger

    logger.debug("Detailed internal state")
    logger.info("Normal application event")
    logger.warning("Unexpected but recoverable")
    logger.error("Operation failed")
    logger.exception("Unexpected error with stack trace")
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from config.settings import (
    LOG_DIRECTORY,
    LOG_FILE,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)

# ── Ensure logs/ folder exists ────────────────────────────────────────────────
os.makedirs(LOG_DIRECTORY, exist_ok=True)

# ── Format ────────────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Build the shared logger ───────────────────────────────────────────────────
logger = logging.getLogger("IRIS")
logger.setLevel(logging.DEBUG)

# Guard against duplicate handlers on re-import
if not logger.handlers:

    # Terminal: INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # File: DEBUG and above, rotates at LOG_MAX_BYTES, keeps LOG_BACKUP_COUNT backups
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
