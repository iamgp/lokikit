"""Tests for kwargs context handling in the logging module."""

import pytest


@pytest.fixture
def context_logger(monkeypatch):
    """Fixture to capture context from logger calls."""
    from lokikit.logger import logger

    captured_contexts = []
    original_info = logger.info

    def patched_info(message, *args, **kwargs):
        # Extract context from kwargs
        context = kwargs.pop("context", {}) if "context" in kwargs else {}

        # Add other kwargs to context
        for key, value in list(kwargs.items()):
            if key not in ("exception", "record"):
                context[key] = value

        # Capture the context
        captured_contexts.append(context)

        # Call original method
        return original_info(message, *args, **kwargs)

    # Patch the info method
    monkeypatch.setattr(logger, "info", patched_info)

    # Return both the logger and the captured contexts
    return logger, captured_contexts


def test_direct_kwargs(context_logger):
    """Test that direct kwargs are converted to context."""
    logger, contexts = context_logger
    logger.info("Test message", user_id="12345", request_id="req-123")

    # Check that we captured a context
    assert contexts, "No contexts captured"

    # Get the last context
    context = contexts[-1]

    # Check kwargs correctly handled
    assert "user_id" in context
    assert context["user_id"] == "12345"
    assert context["request_id"] == "req-123"


def test_explicit_context(context_logger):
    """Test that explicit context parameter works."""
    logger, contexts = context_logger
    logger.info("Test message", context={"user_id": "12345", "request_id": "req-123"})

    # Check that we captured a context
    assert contexts, "No contexts captured"

    # Get the last context
    context = contexts[-1]

    # Check kwargs correctly handled
    assert "user_id" in context
    assert context["user_id"] == "12345"
    assert context["request_id"] == "req-123"


def test_mixed_kwargs_and_context(context_logger):
    """Test that mixing kwargs and context works."""
    logger, contexts = context_logger
    logger.info("Test message", user_id="12345", context={"request_id": "req-123"})

    # Check that we captured a context
    assert contexts, "No contexts captured"

    # Get the last context
    context = contexts[-1]

    # Check kwargs correctly handled
    assert "user_id" in context
    assert context["user_id"] == "12345"
    assert context["request_id"] == "req-123"


def test_reserved_kwargs(context_logger):
    """Test that reserved kwargs aren't moved to context."""
    logger, contexts = context_logger
    logger.info("Test message", user_id="12345", exception=ValueError("Test exception"))

    # Check that we captured a context
    assert contexts, "No contexts captured"

    # Get the last context
    context = contexts[-1]

    # Check context has user_id but not exception
    assert "user_id" in context
    assert context["user_id"] == "12345"
    assert "exception" not in context
