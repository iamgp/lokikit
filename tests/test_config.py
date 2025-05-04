"""Tests for the LokiKit config module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from lokikit.config import (
    ensure_dir,
    load_config_file,
    merge_config,
    update_promtail_config,
    write_config,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    # Cleanup after test completes
    if os.path.exists(dir_path):
        os.rmdir(dir_path)


@pytest.fixture
def test_config_file(temp_dir):
    """Create a test config file."""
    test_config_path = os.path.join(temp_dir, "test_config.yaml")
    test_config = {
        "base_dir": "/tmp/lokikit_test",
        "host": "0.0.0.0",
        "grafana_port": 4000,
        "loki_port": 4100,
        "promtail_port": 9090,
    }

    # Create a test config file
    with open(test_config_path, "w") as f:
        yaml.dump(test_config, f)

    yield test_config_path, test_config

    # Cleanup
    if os.path.exists(test_config_path):
        os.remove(test_config_path)


@pytest.fixture
def promtail_config_file(temp_dir):
    """Create a test promtail config file."""
    config_path = os.path.join(temp_dir, "promtail-config.yaml")

    # Basic Promtail config
    promtail_config = {
        "server": {"http_listen_port": 9080, "http_listen_address": "127.0.0.1"},
        "clients": [{"url": "http://127.0.0.1:3100/loki/api/v1/push"}],
        "scrape_configs": [
            {
                "job_name": "system",
                "static_configs": [
                    {
                        "targets": ["localhost"],
                        "labels": {"job": "varlogs", "__path__": "/var/log/*.log"},
                    }
                ],
            }
        ],
    }

    with open(config_path, "w") as f:
        yaml.dump(promtail_config, f)

    yield config_path, promtail_config

    # Cleanup
    if os.path.exists(config_path):
        os.remove(config_path)


# Test Config Loading


def test_load_config_file_success(test_config_file):
    """Test loading a valid config file."""
    test_config_path, test_config = test_config_file
    config = load_config_file(test_config_path)
    assert config == test_config


def test_load_config_file_nonexistent():
    """Test loading a nonexistent config file."""
    with patch("builtins.print") as mock_print:
        config = load_config_file("/nonexistent/path")
        assert config == {}
        mock_print.assert_called_once()


def test_load_config_file_invalid(test_config_file):
    """Test loading an invalid YAML file."""
    test_config_path, _ = test_config_file

    with open(test_config_path, "w") as f:
        f.write("invalid: yaml: content:")

    with patch("builtins.print") as mock_print:
        config = load_config_file(test_config_path)
        assert config == {}
        mock_print.assert_called_once()


def test_load_config_file_empty(test_config_file):
    """Test loading an empty config file."""
    test_config_path, _ = test_config_file

    with open(test_config_path, "w") as f:
        f.write("")

    config = load_config_file(test_config_path)
    assert config == {}


# Test Config Merging


def test_merge_config_cli_priority():
    """Test that CLI options override file config."""
    cli_options = {"base_dir": "/cli/path", "host": "localhost", "grafana_port": 5000}
    file_config = {
        "base_dir": "/file/path",
        "host": "0.0.0.0",
        "grafana_port": 3000,
        "loki_port": 3100,
    }

    result = merge_config(cli_options, file_config)

    # CLI options should override file config
    assert result["base_dir"] == "/cli/path"
    assert result["host"] == "localhost"
    assert result["grafana_port"] == 5000

    # File config values not in CLI should be preserved
    assert result["loki_port"] == 3100


def test_merge_config_with_none_values():
    """Test merging with None values in CLI options."""
    cli_options = {"base_dir": None, "host": "localhost", "grafana_port": None}
    file_config = {"base_dir": "/file/path", "host": "0.0.0.0", "grafana_port": 3000}

    result = merge_config(cli_options, file_config)

    # None values in CLI should not override file config
    assert result["base_dir"] == "/file/path"
    assert result["host"] == "localhost"  # This should still be overridden
    assert result["grafana_port"] == 3000


def test_merge_config_with_empty_file_config():
    """Test merging with empty file config."""
    cli_options = {"base_dir": "/cli/path", "host": "localhost"}

    result = merge_config(cli_options, {})

    assert result["base_dir"] == "/cli/path"
    assert result["host"] == "localhost"
    assert len(result) == 2  # Only CLI options should be present


# Test Config Utilities


def test_write_config(temp_dir):
    """Test writing config to a file."""
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    content = "Test content"
    write_config(test_file_path, content)

    with open(test_file_path) as f:
        read_content = f.read()

    assert read_content == content

    # Cleanup
    if os.path.exists(test_file_path):
        os.remove(test_file_path)


def test_ensure_dir_existing(temp_dir):
    """Test ensuring an existing directory."""
    # Temp dir already exists
    ensure_dir(temp_dir)
    assert os.path.exists(temp_dir)


def test_ensure_dir_new(temp_dir):
    """Test creating a new directory."""
    new_dir = os.path.join(temp_dir, "new_dir")
    ensure_dir(new_dir)
    assert os.path.exists(new_dir)

    # Cleanup
    if os.path.exists(new_dir):
        os.rmdir(new_dir)


# Test Promtail Configuration


@patch("lokikit.logger.get_logger")
def test_update_promtail_config_new_path(mock_get_logger, promtail_config_file, temp_dir):
    """Test adding a new log path to Promtail config."""
    config_path, _ = promtail_config_file
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    # Add a new log path
    result = update_promtail_config(temp_dir, "/tmp/test.log", job_name="test_job", labels={"app": "test_app"})

    assert result
    mock_logger.info.assert_called()

    # Check the updated config
    with open(config_path) as f:
        updated_config = yaml.safe_load(f)

    # Should now have 2 scrape configs
    assert len(updated_config["scrape_configs"]) == 2

    # Find our new job
    new_job = None
    for job in updated_config["scrape_configs"]:
        if job["job_name"] == "test_job":
            new_job = job

    assert new_job is not None
    assert new_job["static_configs"][0]["labels"]["app"] == "test_app"
    assert "/tmp/test.log" in new_job["static_configs"][0]["labels"]["__path__"]


@patch("lokikit.logger.get_logger")
def test_update_promtail_config_path_exists(mock_get_logger, promtail_config_file, temp_dir):
    """Test handling when a path already exists in the config."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    # First add a path
    result1 = update_promtail_config(temp_dir, "/tmp/test.log", job_name="test_job", labels={"app": "test_app"})

    # Now try to add the same path again
    result2 = update_promtail_config(temp_dir, "/tmp/test.log", job_name="another_job", labels={"app": "another_app"})

    # The first one should succeed, but the second one should fail
    # because the path already exists
    assert result1
    assert not result2

    # The info message about path already being watched should be logged
    mock_logger.info.assert_any_call("Path /tmp/test.log is already being watched.")


@patch("lokikit.logger.get_logger")
def test_update_promtail_config_missing_file(mock_get_logger, temp_dir):
    """Test updating a missing Promtail config file."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    # Try to update a non-existent config
    result = update_promtail_config(
        os.path.join(temp_dir, "nonexistent"),
        "/tmp/test.log",
        job_name="test_job",
        labels={"app": "test_app"},
    )

    assert not result
    mock_logger.error.assert_called()


@patch("lokikit.logger.get_logger")
def test_update_promtail_config_invalid_file(mock_get_logger, temp_dir):
    """Test updating an invalid Promtail config file."""
    invalid_config_path = os.path.join(temp_dir, "promtail-config.yaml")

    # Create an invalid YAML file
    with open(invalid_config_path, "w") as f:
        f.write("invalid: yaml: content:")

    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    result = update_promtail_config(temp_dir, "/tmp/test.log", job_name="test_job", labels={"app": "test_app"})

    assert not result
    mock_logger.error.assert_called()

    # Cleanup
    if os.path.exists(invalid_config_path):
        os.remove(invalid_config_path)


@patch("lokikit.logger.get_logger")
def test_update_promtail_config_empty_file(mock_get_logger, temp_dir):
    """Test updating an empty Promtail config file."""
    empty_config_path = os.path.join(temp_dir, "promtail-config.yaml")

    # Create an empty file
    with open(empty_config_path, "w") as f:
        f.write("")

    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    result = update_promtail_config(temp_dir, "/tmp/test.log", job_name="test_job", labels={"app": "test_app"})

    assert not result
    mock_logger.error.assert_called()

    # Cleanup
    if os.path.exists(empty_config_path):
        os.remove(empty_config_path)


@patch("lokikit.logger.get_logger")
def test_update_promtail_config_importing_error(mock_get_logger):
    """Test handling of importing errors during Promtail config update."""
    MagicMock()
    mock_get_logger.side_effect = ImportError("Mocked import error")

    # This should fall back to using a simple logger
    result = update_promtail_config(
        "/nonexistent/dir", "/tmp/test.log", job_name="test_job", labels={"app": "test_app"}
    )

    # Should return False because the config file doesn't exist
    assert not result
