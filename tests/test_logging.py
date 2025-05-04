"""Tests for the LokiKit logging module."""

import json
import logging as standard_logging
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from lokikit.logger import get_version, setup_logging


@pytest.fixture
def temp_log_dir():
    """Set up a temporary directory for test logs."""
    temp_dir = tempfile.mkdtemp()
    logs_dir = os.path.join(temp_dir, "logs")
    yield temp_dir, logs_dir


def test_directory_creation(temp_log_dir):
    """Test that the logs directory is created."""
    temp_dir, logs_dir = temp_log_dir
    setup_logging(temp_dir, verbose=False)
    assert os.path.isdir(logs_dir), "Logs directory not created"


def test_log_file_creation(temp_log_dir):
    """Test that a log file is created when logging."""
    temp_dir, logs_dir = temp_log_dir
    logger = setup_logging(temp_dir, verbose=True)
    logger.info("Test message")

    # Find the created log file
    files = os.listdir(logs_dir)
    assert files, "No log files were created"
    assert any(f.startswith("lokikit_") and f.endswith(".log") for f in files), "No lokikit log file found"


@pytest.fixture
def logging_setup():
    """Set up a specific log file and configure logging."""
    temp_dir = tempfile.mkdtemp()
    log_file = os.path.join(temp_dir, "test_log.log")

    serializer = None

    # Set up mock for log file
    with patch("lokikit.logger.logger.add") as mock_add:
        # Capture the serializer function when logger.add is called
        def capture_serializer(*args, **kwargs):
            nonlocal serializer
            serializer = kwargs.get("serialize")

        mock_add.side_effect = capture_serializer

        # Mock datetime for time field that's JSON serializable
        mock_time = MagicMock()
        mock_time.isoformat.return_value = "2023-01-01T12:00:00"

        # Mock for level that provides the name property properly
        mock_level = MagicMock()
        mock_level.name = "INFO"

        # Mock for file path that provides path attribute properly
        mock_file = MagicMock()
        mock_file.path = "/test/file.py"

        # Mock record for testing serializer with properly structured data
        mock_record = {
            "time": mock_time,
            "level": mock_level,
            "name": "test_logger",
            "message": "Test message",
            "file": mock_file,
            "line": 42,
            "function": "test_function",
            "exception": None,
            "extra": {},
        }

        # Set up the logger
        setup_logging(temp_dir, verbose=True)

        yield temp_dir, log_file, serializer, mock_record


def test_json_serialization(logging_setup):
    """Test that logs are properly serialized to JSON."""
    _, _, serializer, mock_record = logging_setup

    # Ensure serializer was captured
    assert serializer is not None, "Serializer function not captured"

    # Test with basic record
    json_str = serializer(mock_record)
    log_data = json.loads(json_str)

    # Check required fields
    assert "timestamp" in log_data
    assert "level" in log_data
    assert "message" in log_data
    assert "location" in log_data
    assert "service" in log_data
    assert "version" in log_data

    # Check message content
    assert log_data["message"] == "Test message"


def test_context_serialization(logging_setup):
    """Test that context is properly included in JSON output."""
    _, _, serializer, mock_record = logging_setup

    # Test record with context
    mock_record["extra"] = {"context": {"user_id": "12345", "request_id": "req-123"}}

    json_str = serializer(mock_record)
    log_data = json.loads(json_str)

    # Check context is included
    assert "context" in log_data
    assert log_data["context"]["user_id"] == "12345"
    assert log_data["context"]["request_id"] == "req-123"


def test_exception_serialization(logging_setup):
    """Test that exceptions are properly included in JSON output."""
    _, _, serializer, mock_record = logging_setup

    # Test record with exception
    mock_record["exception"] = "Traceback info here"

    json_str = serializer(mock_record)
    log_data = json.loads(json_str)

    # Check exception is included
    assert "exception" in log_data
    assert log_data["exception"] == "Traceback info here"


def test_intercept_handler():
    """Test that InterceptHandler forwards messages to loguru."""
    with patch("lokikit.logger.logger.opt") as mock_opt:
        # Create a standard logging record
        record = standard_logging.LogRecord(
            name="test_logger",
            level=standard_logging.INFO,
            pathname="/test/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Set up mock for the bound logger
        mock_bound_logger = MagicMock()
        mock_opt.return_value = mock_bound_logger

        # Import handler and call emit
        from lokikit.logger import InterceptHandler

        handler = InterceptHandler()
        handler.emit(record)

        # Check that logger.opt was called
        mock_opt.assert_called_once()
        # Check that log was called on the bound logger
        mock_bound_logger.log.assert_called_once()


def test_get_version_success():
    """Test successful version retrieval."""
    with patch("importlib.metadata.version") as mock_version:
        mock_version.return_value = "1.2.3"
        assert get_version() == "1.2.3"


def test_get_version_failure():
    """Test version retrieval failure handling."""
    with patch("importlib.metadata.version", side_effect=Exception("Test error")):
        assert get_version() == "unknown"
