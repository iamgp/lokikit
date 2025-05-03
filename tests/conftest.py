"""Common pytest fixtures for LokiKit tests."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    # Clean up the directory after test completes
    if os.path.exists(dir_path):
        os.rmdir(dir_path)


@pytest.fixture
def mock_logger():
    """Set up logger mock that can be used across tests."""
    with patch('lokikit.config.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger
