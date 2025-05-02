"""Logging configuration for lokikit using Loguru."""

import os
import sys
import json
from datetime import datetime
from functools import wraps, partial

try:
    from loguru import logger
except ImportError:
    # Add loguru to dependencies in setup.py
    raise ImportError(
        "Loguru is required for LokiKit logging. "
        "Please install it with: pip install loguru"
    )


# Patch Loguru logger to support direct kwargs as context
def _patch_loguru_methods():
    """Patch loguru methods to support context fields as direct kwargs."""
    log_methods = ["trace", "debug", "info", "success", "warning", "error", "critical", "exception"]

    for method_name in log_methods:
        original_method = getattr(logger, method_name)

        # Create a new method with the same signature but supporting kwargs as context
        def patched_method(original_func, message, *args, **kwargs):
            # Extract any context provided
            context_kwargs = kwargs.pop("context", {})

            # Add any remaining kwargs to context
            for key, value in kwargs.items():
                context_kwargs[key] = value

            # If we have context, bind it
            if context_kwargs:
                bound_logger = original_func.__self__.bind(context=context_kwargs)
                bound_logger(message, *args)
            else:
                original_func(message, *args)

        # Create a partial function with the original method
        method_with_original = partial(patched_method, original_method)

        # Use update_wrapper instead of wraps to maintain function signature
        wraps(original_method)(method_with_original)

        # Replace the original method
        setattr(logger, method_name, method_with_original)


def setup_logging(base_dir, verbose=False):
    """Configure logging for lokikit using Loguru.

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

    # Clear existing handlers
    logger.remove()

    # Configure log level
    log_level = "DEBUG" if verbose else "INFO"

    # Add console sink with minimal format (message only)
    logger.add(
        sys.stdout,
        level="INFO",
        format="{message}",  # Super minimal output
    )

    # Add JSON file sink with structured logging
    log_file = os.path.join(logs_dir, f"lokikit_{datetime.now().strftime('%Y%m%d')}.log")

    def json_serializer(record):
        """Serialize log record to JSON with LokiKit-specific structure."""
        # Standard log data
        log_data = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "message": record["message"],
            "location": {
                "file": record["file"].path,
                "line": record["line"],
                "function": record["function"],
            },
            "service": "lokikit",
            "version": get_version(),
        }

        # Add exception info if present
        if record["exception"]:
            log_data["exception"] = record["exception"]

        # Add extra contextual data
        for key, value in record["extra"].items():
            if key == "context" and isinstance(value, dict):
                log_data["context"] = value
            else:
                log_data[key] = value

        return json.dumps(log_data)

    logger.add(
        log_file,
        level=log_level,
        format="{message}",  # Content will be replaced by serializer
        serialize=json_serializer,
        rotation="10 MB",
        retention="1 week",
    )

    # Patch loguru methods to support kwargs as context
    _patch_loguru_methods()

    return logger


def get_version() -> str:
    """Get the version of lokikit.

    Returns:
        Version string or 'unknown' if not available
    """
    try:
        from importlib.metadata import version
        return version("lokikit")
    except:
        return "unknown"


def get_logger():
    """Get the lokikit logger.

    Returns:
        Loguru logger instance
    """
    return logger


# Patch existing code that might use the standard logging module
import logging

class InterceptHandler(logging.Handler):
    """
    Intercept standard logging messages toward Loguru.

    This allows existing code using the standard logging module
    to work with our Loguru setup.
    """

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

# Configure standard logging to use Loguru
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
