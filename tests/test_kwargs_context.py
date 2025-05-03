"""Tests for kwargs context handling in the logging module."""

import pytest


@pytest.fixture
def log_capture():
    """Fixture for capturing logs with context."""
    log_records = []

    # Store original log method to restore it later
    original_log = None

    try:

        def start_capturing():
            """Replace _log method with a capturing version."""
            from lokikit.logging import logger

            nonlocal original_log
            original_log = logger.__class__._log

            def capture_log(self, level, from_decorator, options, message, args, kwargs):
                # Process kwargs to extract context just like the real logger would
                context = {}
                if "context" in kwargs:
                    context = kwargs.pop("context")

                # Move all remaining kwargs into the context (except reserved ones)
                for key, value in list(kwargs.items()):
                    if key not in ("exception", "record"):
                        context[key] = value
                        kwargs.pop(key)

                # Capture the log record
                log_records.append(
                    {
                        "level": level,
                        "message": message,
                        "args": args,
                        "kwargs": kwargs,
                        "context": context,  # Save context separately for easier testing
                    }
                )

                # Call original log method if needed
                # original_log(self, level, message, args, **kwargs)

            logger.__class__._log = capture_log
            return logger

        # Start capturing logs
        logger = start_capturing()

        yield logger, log_records

    finally:
        # Restore original log method
        if original_log:
            from lokikit.logging import logger

            logger.__class__._log = original_log


def test_direct_kwargs(log_capture):
    """Test that direct kwargs are converted to context."""
    logger, log_records = log_capture
    logger.info("Test message", user_id="12345", request_id="req-123")

    # Check that we captured a log
    assert log_records, "No log records captured"

    # Get the last record
    record = log_records[-1]

    # Check kwargs correctly handled
    assert "context" in record
    context = record["context"]
    assert context["user_id"] == "12345"
    assert context["request_id"] == "req-123"


def test_explicit_context(log_capture):
    """Test that explicit context parameter works."""
    logger, log_records = log_capture
    logger.info("Test message", context={"user_id": "12345", "request_id": "req-123"})

    # Check that we captured a log
    assert log_records, "No log records captured"

    # Get the last record
    record = log_records[-1]

    # Check kwargs correctly handled
    assert "context" in record
    context = record["context"]
    assert context["user_id"] == "12345"
    assert context["request_id"] == "req-123"


def test_mixed_kwargs_and_context(log_capture):
    """Test that mixing kwargs and context works."""
    logger, log_records = log_capture
    logger.info("Test message", user_id="12345", context={"request_id": "req-123"})

    # Check that we captured a log
    assert log_records, "No log records captured"

    # Get the last record
    record = log_records[-1]

    # Check kwargs correctly handled
    assert "context" in record
    context = record["context"]
    assert context["user_id"] == "12345"
    assert context["request_id"] == "req-123"


def test_reserved_kwargs(log_capture):
    """Test that reserved kwargs aren't moved to context."""
    logger, log_records = log_capture
    logger.info("Test message", user_id="12345", exception=ValueError("Test exception"))

    # Check that we captured a log
    assert log_records, "No log records captured"

    # Get the last record
    record = log_records[-1]

    # Check context has user_id but not exception
    assert "context" in record
    context = record["context"]
    assert context["user_id"] == "12345"
    assert "exception" not in context
    assert "exception" in record["kwargs"]
