"""Recommended logging configuration for applications using LokiKit.

This module provides a standardized logging setup that works well with LokiKit
and Grafana visualization. It uses structured JSON logging to enable powerful
querying with LogQL.
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union


class StructuredJsonFormatter(logging.Formatter):
    """Custom formatter that outputs logs as structured JSON.

    This format works well with Loki's LogQL for efficient querying and filtering.
    """

    def __init__(self, service_name: str, additional_fields: Optional[Dict[str, Any]] = None):
        """Initialize the formatter with service info and additional fields.

        Args:
            service_name: Name of the service/application
            additional_fields: Static fields to include with every log message
        """
        super().__init__()
        self.service_name = service_name
        self.additional_fields = additional_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data = {
            # Standard fields - useful for filtering and sorting
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "thread": record.threadName,
            "service": self.service_name,
            "message": record.getMessage(),
            # Add file and line information for debugging
            "location": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
        }

        # Add custom fields from record attributes
        if hasattr(record, "context") and isinstance(record.context, dict):
            log_data["context"] = record.context

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add any fields passed to logger.log(..., extra={...})
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in (
                    "args",
                    "asctime",
                    "created",
                    "exc_info",
                    "exc_text",
                    "filename",
                    "funcName",
                    "id",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "msg",
                    "name",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "thread",
                    "threadName",
                    "context",
                ):
                    log_data[key] = value

        # Add any additional fields from initialization
        log_data.update(self.additional_fields)

        # Return the log entry as a JSON string
        return json.dumps(log_data)


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that allows adding context to log messages.

    Provides a way to add structured context data to log entries.
    """

    def __init__(self, logger: logging.Logger, context: Optional[Dict[str, Any]] = None):
        """Initialize the adapter with a logger and optional context.

        Args:
            logger: The logger to wrap
            context: Initial context dict to include with all messages
        """
        super().__init__(logger, context or {})

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process the log message to add context information.

        Args:
            msg: The log message
            kwargs: Additional arguments for the logger

        Returns:
            Tuple of (message, keyword args)
        """
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        if "context" not in kwargs["extra"]:
            kwargs["extra"]["context"] = {}

        # Add adapter's context to the record's context
        kwargs["extra"]["context"].update(self.extra)

        return msg, kwargs

    def bind(self, **kwargs) -> "ContextAdapter":
        """Create a new logger with additional context values.

        Args:
            **kwargs: Context key-value pairs to add

        Returns:
            New ContextAdapter with combined context
        """
        new_context = self.extra.copy()
        new_context.update(kwargs)
        return ContextAdapter(self.logger, new_context)


def setup_structured_logging(
    service_name: str,
    log_level: Union[int, str] = logging.INFO,
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    additional_fields: Optional[Dict[str, Any]] = None,
    root_logger: bool = True,
) -> ContextAdapter:
    """Configure structured JSON logging suitable for LokiKit.

    Args:
        service_name: Name of the service/application
        log_level: Minimum log level to capture
        log_file: Path to log file, if None will only log to console
        log_to_console: Whether to output logs to console
        additional_fields: Dict of fields to include with every log message
        root_logger: Whether to configure the root logger

    Returns:
        ContextAdapter for the configured logger
    """
    # Create formatter
    formatter = StructuredJsonFormatter(service_name, additional_fields)

    # Get or create logger
    logger_name = None if root_logger else service_name
    logger = logging.getLogger(logger_name)

    # Set log level
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicate logs
    logger.handlers = []

    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if a log file is specified
    if log_file:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Return a context adapter for the logger
    return ContextAdapter(logger)


def get_logger(module_name: str, context: Optional[Dict[str, Any]] = None) -> ContextAdapter:
    """Get a logger with context for a specific module.

    Args:
        module_name: Name of the module/component requesting the logger
        context: Optional initial context for the logger

    Returns:
        ContextAdapter with the specified context
    """
    logger = logging.getLogger(module_name)
    return ContextAdapter(logger, context or {})


# Example usage
if __name__ == "__main__":
    # Setup logging for the whole application
    logger = setup_structured_logging(
        service_name="my-application",
        log_level=logging.DEBUG,
        log_file="logs/application.log",
        additional_fields={
            "environment": "development",
            "version": "1.0.0",
        },
    )

    # Simple usage
    logger.info("Application started")

    # With additional context
    user_logger = logger.bind(user_id="12345")
    user_logger.info("User logged in")

    # With temporary context
    logger.info("Processing order", extra={"context": {"order_id": "ORD-123456"}})

    # Using the context in exception handling
    try:
        result = 1 / 0
    except Exception:
        logger.exception(
            "An error occurred during calculation", extra={"context": {"operation": "division"}}
        )

# Sample LogQL queries for effective filtering in Grafana:
#
# 1. Filter by log level:
#    {job="my-application"} | json | level="ERROR"
#
# 2. Filter by service and context:
#    {job="my-application"} | json | service="my-application" and context.user_id="12345"
#
# 3. Search in message field:
#    {job="my-application"} | json | message=~".*error.*"
#
# 4. Analyze exceptions:
#    {job="my-application"} | json | exception.type="ZeroDivisionError"
#
# 5. Combined filtering:
#    {job="my-application"} | json | level="ERROR" and context.order_id="ORD-123456"
