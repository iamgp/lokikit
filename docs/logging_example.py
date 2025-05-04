#!/usr/bin/env python3
"""Example usage of lokikit's Loguru-based logging.

This demonstrates how to use the updated lokikit logging module
that uses Loguru with structured JSON for log files while
keeping console output minimal.
"""

import os
from datetime import datetime

from lokikit.logger import get_logger, setup_logging

# Assuming we're running from the project root
base_dir = os.path.expanduser("~/.lokikit")

# Set up logging with Loguru
setup_logging(base_dir, verbose=True)
logger = get_logger()

# Basic logging examples
logger.info("Starting example application")
logger.debug("This debug message will appear in the log file but not console")
logger.warning("Warning: this is a warning message")

# Using direct kwargs for context (simplest approach)
logger.info("Processing configuration file", file_path="/etc/myapp/config.yaml", environment="development")

# You can still use the explicit context parameter if preferred
logger.info("User profile loaded", context={"user_id": "12345", "session_id": "abc-123"})

# Advanced: create a contextualized logger with bind
user_logger = logger.bind(context={"user_id": "12345", "session_id": "abc-123"})
user_logger.info("User logged in")
user_logger.debug("Session details loaded")

# Adding more context with kwargs to a bound logger
user_logger.info("User updated profile", action="profile_update", changes=["email", "avatar"])

# Error logging with exception information
try:
    result = 1 / 0
except Exception:
    # Loguru automatically captures exception information
    logger.exception("An error occurred during calculation")

    # With additional context via kwargs
    logger.error(
        "Failed to perform division operation",
        operation="division",
        operands=[1, 0],
        component="calculator",
    )

# You can also temporarily add context using with statement
with logger.contextualize(context={"request_id": "req-456", "api": "users"}):
    logger.info("Processing API request")
    logger.debug("Request validated")

    # Add more context via kwargs within the contextualized block
    logger.info("API request completed", status_code=200, response_time_ms=42)

logger.success("Application completed successfully")  # Loguru has more log levels!

print("\nCheck the log file at: " + os.path.join(base_dir, "logs", f"lokikit_{datetime.now().strftime('%Y%m%d')}.log"))
print("The log file contains structured JSON that will work well with Loki queries.")
print("Example LogQL queries:")
print('  {job="lokikit"} | json | level="ERROR"')
print('  {job="lokikit"} | json | context.user_id="12345"')
print('  {job="lokikit"} | json | context.component="calculator"')

# Example LogQL queries for this structured logging:
#
# Find all errors:
# {job="lokikit"} | json | level="ERROR"
#
# Find logs with specific context:
# {job="lokikit"} | json | context.environment="development"
#
# Find logs for a specific user:
# {job="lokikit"} | json | context.user_id="12345"
#
# Find logs with specific status code:
# {job="lokikit"} | json | context.status_code=200
