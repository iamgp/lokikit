"""Logging configuration for lokikit."""

import os
import logging
import logging.handlers
from datetime import datetime


def setup_logging(base_dir, verbose=False):
    """Configure logging for lokikit.

    Args:
        base_dir: Base directory for lokikit, where logs will be stored
        verbose: Whether to enable debug logging

    Returns:
        The configured logger instance
    """
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(base_dir, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Create a logger
    logger = logging.getLogger("lokikit")

    # Set level based on verbose flag
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Add a file handler that logs to a dated file
    log_file = os.path.join(logs_dir, f"lokikit_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5
    )

    # Add a console handler for STDOUT output
    console_handler = logging.StreamHandler()

    # Configure formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Use a simple formatter that only includes the message for console output
    console_formatter = logging.Formatter('%(message)s')

    # Add formatters to handlers
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    # Set console handler level (show only INFO and above in console)
    console_handler.setLevel(logging.INFO)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger():
    """Get the lokikit logger.

    Returns:
        Logger instance for lokikit
    """
    return logging.getLogger("lokikit")
