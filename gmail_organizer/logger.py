"""Logging configuration for Gmail Organizer"""

import logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist (at project root)
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Create log filename with timestamp
LOG_FILE = os.path.join(LOGS_DIR, f'gmail_organizer_{datetime.now().strftime("%Y%m%d")}.log')


def setup_logger(name='gmail_organizer'):
    """Set up and return a configured logger"""
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # File handler - logs everything to file
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        # Console handler - logs INFO and above to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# Create default logger
logger = setup_logger()
