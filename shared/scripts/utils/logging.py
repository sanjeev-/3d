"""
Logging utilities with colored output.
"""

import logging
import sys
from typing import Optional

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output."""

    def __init__(self, fmt: str):
        super().__init__()
        self.fmt = fmt

        if COLORAMA_AVAILABLE:
            self.FORMATS = {
                logging.DEBUG: Fore.CYAN + self.fmt + Style.RESET_ALL,
                logging.INFO: Fore.GREEN + self.fmt + Style.RESET_ALL,
                logging.WARNING: Fore.YELLOW + self.fmt + Style.RESET_ALL,
                logging.ERROR: Fore.RED + self.fmt + Style.RESET_ALL,
                logging.CRITICAL: Fore.RED + Style.BRIGHT + self.fmt + Style.RESET_ALL,
            }
        else:
            self.FORMATS = {level: self.fmt for level in [
                logging.DEBUG, logging.INFO, logging.WARNING,
                logging.ERROR, logging.CRITICAL
            ]}

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logger(name: str = "blender_movies",
                level: int = logging.INFO,
                log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger with colored console output.

    Args:
        name: Logger name
        level: Logging level
        log_file: Optional file path for log output

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Console handler with color
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (no color)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "blender_movies") -> logging.Logger:
    """
    Get an existing logger or create a new one.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    # Set up logger if it doesn't have handlers
    if not logger.handlers:
        setup_logger(name)

    return logger
