"""Logging configuration for lokikit using Loguru."""

import json
import logging
import os
import sys
import unittest.mock
from datetime import datetime
from typing import Any

try:
    from loguru import logger
except ImportError as e:
    # Add loguru to dependencies in setup.py
    raise ImportError("Loguru is required for LokiKit logging. Please install it with: pip install loguru") from e


class LokiKitJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle mock objects for testing."""

    def default(self, obj):
        """Handle non-serializable objects."""
        if isinstance(obj, unittest.mock.Mock):
            # For mock objects, try to get a string representation or specific attributes
            if hasattr(obj, "name") and obj.name:
                return obj.name
            if hasattr(obj, "path") and obj.path:
                return obj.path
            if hasattr(obj, "isoformat") and callable(obj.isoformat):
                return obj.isoformat()
            return str(obj)

        # Handle datetime objects
        if hasattr(obj, "isoformat") and callable(obj.isoformat):
            return obj.isoformat()

        # Let the base class handle other types or raise TypeError
        return super().default(obj)


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

    def json_serializer(record: dict[str, Any]) -> str:
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

        return json.dumps(log_data, cls=LokiKitJSONEncoder)

    logger.add(
        log_file,
        level=log_level,
        format="{message}",  # Content will be replaced by serializer
        serialize=json_serializer,  # type: ignore # Loguru allows callable for serialize
        rotation="10 MB",
        retention="1 week",
    )

    # Enable handling of context from kwargs by intercepting log calls
    _patch_logger_for_kwargs()

    return logger


def _patch_logger_for_kwargs():
    """Patch the logger to support direct kwargs as context."""
    # Use monkey patching at the module level instead of modifying the class

    # Store the original logger.info, debug, warning, etc. methods
    original_methods = {}

    for level in ["trace", "debug", "info", "success", "warning", "error", "critical"]:
        original_methods[level] = getattr(logger, level)

        # Create a new method that handles kwargs as context
        def create_patched_method(original_method, level_name):
            def patched_method(message, *args, **kwargs):
                # Extract explicit context if provided
                context = kwargs.pop("context", {})

                # Move all remaining kwargs into the context
                for key, value in list(kwargs.items()):
                    if key not in ("exception", "record"):
                        context[key] = value
                        kwargs.pop(key)

                # If we have context, add it to the extra dict
                if context:
                    if "extra" not in kwargs:
                        kwargs["extra"] = {"context": context}
                    else:
                        kwargs["extra"]["context"] = context

                # Call the original method
                return original_method(message, *args, **kwargs)

            return patched_method

        # Replace the method with our patched version
        setattr(logger, level, create_patched_method(original_methods[level], level))


def get_version() -> str:
    """Get the version of lokikit.

    Returns:
        Version string or 'unknown' if not available
    """
    try:
        from importlib.metadata import version

        return version("lokikit")
    except Exception:
        return "unknown"


def get_logger():
    """Get the lokikit logger.

    Returns:
        Loguru logger instance
    """
    return logger


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
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Configure standard logging to use Loguru
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
