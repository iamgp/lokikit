"""Tests for the LokiKit commands module."""

import os
import tempfile
import platform
import pytest
from unittest.mock import patch, MagicMock, call, mock_open
import asyncio
from typing import cast, List
import unittest.mock
import sys
import yaml

from lokikit.commands import setup_command, start_command, stop_command, status_command, watch_command, clean_command, force_quit_command


@pytest.fixture
def setup_test_env():
    """Set up test environment for setup command tests."""
    temp_dir = tempfile.mkdtemp()
    # Create mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "HOST": "127.0.0.1",
        "GRAFANA_PORT": 3000,
        "LOKI_PORT": 3100,
        "PROMTAIL_PORT": 9080,
        "CONFIG": {}
    }

    # Setup logger mock
    with patch('lokikit.commands.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        yield ctx, temp_dir, mock_logger

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(temp_dir)


@pytest.mark.parametrize("binaries_exist", [False, True])
@patch('lokikit.commands.get_binaries')
@patch('lokikit.commands.download_and_extract')
@patch('lokikit.commands.find_grafana_binary')
@patch('lokikit.commands.ensure_dir')
@patch('lokikit.commands.write_config')
@patch('os.chmod')
@patch('os.path.exists')
@patch('builtins.open', new_callable=unittest.mock.mock_open)
def test_setup_command(mock_open, mock_exists, mock_chmod, mock_write_config,
                       mock_ensure_dir, mock_find_grafana,
                       mock_download, mock_get_binaries,
                       setup_test_env, binaries_exist):
    """Test setup command execution with various conditions."""
    ctx, temp_dir, mock_logger = setup_test_env

    # Mock binary information
    binaries = {
        "loki": {
            "version": "2.5.0",
            "binary": "loki-linux-amd64",
            "url": "https://example.com/loki.zip",
            "filename": "loki-linux-amd64.zip"
        },
        "promtail": {
            "version": "2.5.0",
            "binary": "promtail-linux-amd64",
            "url": "https://example.com/promtail.zip",
            "filename": "promtail-linux-amd64.zip"
        },
        "grafana": {
            "version": "9.0.0",
            "binary_name": "grafana-server",
            "url": "https://example.com/grafana.tar.gz",
            "filename": "grafana-9.0.0.linux-amd64.tar.gz"
        },
        "os_name": "linux"
    }
    mock_get_binaries.return_value = binaries

    # Mock that binaries exist or don't exist based on parameter
    def exists_side_effect(path):
        if 'conf/provisioning/datasources/lokikit.yaml' in path:
            return False  # Always create the datasource file
        return binaries_exist

    mock_exists.side_effect = exists_side_effect

    # Mock the grafana binary path
    grafana_path = os.path.join(temp_dir, "grafana-9.0.0", "bin", "grafana-server")
    mock_find_grafana.return_value = grafana_path

    # Execute setup command
    setup_command(ctx)

    # Verify directory creation
    mock_ensure_dir.assert_called()

    # Verify binary downloads
    if binaries_exist:
        mock_download.assert_not_called()
    else:
        assert mock_download.call_count == 3  # loki, promtail, grafana
        # For non-existing binaries, verify file permission changes for Unix systems
        assert mock_chmod.call_count == 3  # loki, promtail, grafana

    # Verify config file creation (should happen regardless of whether binaries exist)
    assert mock_write_config.call_count == 2  # loki and promtail configs

    # Verify logging
    mock_logger.info.assert_called()


@patch('lokikit.commands.get_binaries')
@patch('lokikit.commands.download_and_extract')
@patch('lokikit.commands.find_grafana_binary')
@patch('lokikit.commands.ensure_dir')
@patch('lokikit.commands.write_config')
@patch('os.path.exists')
def test_setup_command_with_custom_log_paths(mock_exists, mock_write_config,
                                          mock_ensure_dir, mock_find_grafana,
                                          mock_download, mock_get_binaries,
                                          setup_test_env):
    """Test setup command with custom log paths in config."""
    ctx, temp_dir, mock_logger = setup_test_env

    # Mock binary information
    binaries = {
        "loki": {
            "version": "2.5.0",
            "binary": "loki-linux-amd64",
            "url": "https://example.com/loki.zip",
            "filename": "loki-linux-amd64.zip"
        },
        "promtail": {
            "version": "2.5.0",
            "binary": "promtail-linux-amd64",
            "url": "https://example.com/promtail.zip",
            "filename": "promtail-linux-amd64.zip"
        },
        "grafana": {
            "version": "9.0.0",
            "binary_name": "grafana-server",
            "url": "https://example.com/grafana.tar.gz",
            "filename": "grafana-9.0.0.linux-amd64.tar.gz"
        },
        "os_name": "linux"
    }
    mock_get_binaries.return_value = binaries

    # Set up custom log paths in config
    ctx.obj["CONFIG"] = {
        "promtail": {
            "log_paths": [
                {
                    "path": "/var/log/test.log",
                    "labels": {
                        "job": "test"
                    }
                }
            ]
        }
    }

    # Mock that binaries already exist
    mock_exists.return_value = True

    # Mock the grafana binary path
    grafana_path = os.path.join(temp_dir, "grafana-9.0.0", "bin", "grafana-server")
    mock_find_grafana.return_value = grafana_path

    # Execute setup command
    setup_command(ctx)

    # Verify config file writing with custom paths
    assert mock_write_config.call_count == 2  # loki and promtail configs

    # Verify the custom log paths were used in writing the config
    # This check would depend on how the promtail config is structured
    # and might require more granular assertions based on the implementation

    # Verify logging
    mock_logger.info.assert_called()


@pytest.fixture
def start_test_env():
    """Set up test environment for start command tests."""
    temp_dir = tempfile.mkdtemp()

    # Create mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "HOST": "127.0.0.1",
        "GRAFANA_PORT": 3000,
        "LOKI_PORT": 3100,
        "PROMTAIL_PORT": 9080,
        "CONFIG": {}
    }

    # Setup logger mock
    with patch('lokikit.commands.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Path for the pid file
        pid_file = os.path.join(temp_dir, "lokikit.pid")

        # Create fake config files
        os.makedirs(os.path.join(temp_dir, "logs"), exist_ok=True)
        with open(os.path.join(temp_dir, "loki-config.yaml"), "w") as f:
            f.write("test loki config")
        with open(os.path.join(temp_dir, "promtail-config.yaml"), "w") as f:
            f.write("test promtail config")

        yield ctx, temp_dir, mock_logger, pid_file

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(temp_dir)


@patch('lokikit.commands.get_binaries')
@patch('lokikit.commands.get_binary_path')
@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.start_process')
@patch('lokikit.commands.wait_for_services')
@patch('lokikit.commands.write_pid_file')
@patch('lokikit.commands.read_pid_file')
@patch('lokikit.commands.ensure_dir')
@patch('os.path.exists')
@patch('sys.exit')
def test_start_command_foreground(mock_exit, mock_exists, mock_ensure_dir, mock_read_pid, mock_write_pid,
                                 mock_wait, mock_start, mock_check,
                                 mock_get_binary, mock_get_binaries,
                                 start_test_env):
    """Test start command in foreground mode."""
    ctx, temp_dir, mock_logger, pid_file = start_test_env

    # Mock no existing PID file
    mock_read_pid.return_value = None

    # Make ensure_dir not raise errors
    mock_ensure_dir.return_value = None

    # Mock binary information
    binaries = {
        "loki": {"binary": "loki-linux-amd64", "version": "2.5.0"},
        "promtail": {"binary": "promtail-linux-amd64", "version": "2.5.0"},
        "grafana": {"binary_name": "grafana-server", "version": "9.0.0"},
        "os_name": "linux"
    }
    mock_get_binaries.return_value = binaries

    # Mock binary paths
    loki_path = os.path.join(temp_dir, "loki-linux-amd64")
    promtail_path = os.path.join(temp_dir, "promtail-linux-amd64")
    grafana_path = os.path.join(temp_dir, "grafana-server")

    def get_binary_path_side_effect(name, binaries, base_dir):
        if name == "loki":
            return loki_path
        elif name == "promtail":
            return promtail_path
        elif name == "grafana":
            return grafana_path
        return None

    mock_get_binary.side_effect = get_binary_path_side_effect

    # Mock successful wait_for_services
    mock_wait.return_value = True

    # Mock config files exists
    def exists_side_effect(path):
        if path.endswith("lokikit.pid"):
            return False
        return True

    mock_exists.side_effect = exists_side_effect

    # Execute start command in foreground (default)
    start_command(ctx, False, False, 20)

    # Verify the right processes were started
    assert mock_start.call_count == 3  # loki, promtail, grafana

    # Verify wait_for_services was called
    mock_wait.assert_called_once()

    # Verify PID file was written
    mock_write_pid.assert_called_once()


@patch('lokikit.commands.get_binaries')
@patch('lokikit.commands.get_binary_path')
@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.start_process')
@patch('lokikit.commands.wait_for_services')
@patch('lokikit.commands.write_pid_file')
@patch('lokikit.commands.read_pid_file')
@patch('lokikit.commands.ensure_dir')
@patch('os.path.exists')
@patch('sys.exit')
def test_start_command_background(mock_exit, mock_exists, mock_ensure_dir, mock_read_pid, mock_write_pid,
                                 mock_wait, mock_start, mock_check,
                                 mock_get_binary, mock_get_binaries,
                                 start_test_env):
    """Test start command in background mode."""
    ctx, temp_dir, mock_logger, pid_file = start_test_env

    # Mock no existing PID file
    mock_read_pid.return_value = None

    # Make ensure_dir not raise errors
    mock_ensure_dir.return_value = None

    # Mock binary information
    binaries = {
        "loki": {"binary": "loki-linux-amd64", "version": "2.5.0"},
        "promtail": {"binary": "promtail-linux-amd64", "version": "2.5.0"},
        "grafana": {"binary_name": "grafana-server", "version": "9.0.0"},
        "os_name": "linux"
    }
    mock_get_binaries.return_value = binaries

    # Mock binary paths
    loki_path = os.path.join(temp_dir, "loki-linux-amd64")
    promtail_path = os.path.join(temp_dir, "promtail-linux-amd64")
    grafana_path = os.path.join(temp_dir, "grafana-server")

    def get_binary_path_side_effect(name, binaries, base_dir):
        if name == "loki":
            return loki_path
        elif name == "promtail":
            return promtail_path
        elif name == "grafana":
            return grafana_path
        return None

    mock_get_binary.side_effect = get_binary_path_side_effect

    # Mock successful wait_for_services
    mock_wait.return_value = True

    # Mock config files exists
    def exists_side_effect(path):
        if path.endswith("lokikit.pid"):
            return False
        return True

    mock_exists.side_effect = exists_side_effect

    # Execute start command in background
    start_command(ctx, True, False, 20)

    # Verify the right processes were started
    assert mock_start.call_count == 3

    # Since each process can be started with different args, just check
    # that the start_process function was called 3 times

    # Verify wait_for_services was called
    mock_wait.assert_called_once()

    # Verify PID file was written
    mock_write_pid.assert_called_once()


# @patch('lokikit.commands.get_binaries')
# @patch('lokikit.commands.get_binary_path')
# @patch('lokikit.commands.check_services_running')
# @patch('lokikit.commands.start_process')
# @patch('lokikit.commands.wait_for_services')
# @patch('lokikit.commands.write_pid_file')
# @patch('lokikit.commands.read_pid_file')
# @patch('lokikit.commands.ensure_dir')
# @patch('os.path.exists')
# @patch('sys.exit')
# def test_start_command_service_failed(mock_exit, mock_exists, mock_ensure_dir,
#                                      mock_read_pid, mock_write_pid, mock_wait, mock_start, mock_check,
#                                      mock_get_binary, mock_get_binaries,
#                                      start_test_env):
#     """Test start command when a service fails to start."""
#     ctx, temp_dir, mock_logger, pid_file = start_test_env

#     # Mock no existing PID file
#     mock_read_pid.return_value = None

#     # Make ensure_dir not raise errors
#     mock_ensure_dir.return_value = None

#     # Mock binary information
#     binaries = {
#         "loki": {"binary": "loki-linux-amd64", "version": "2.5.0"},
#         "promtail": {"binary": "promtail-linux-amd64", "version": "2.5.0"},
#         "grafana": {"binary_name": "grafana-server", "version": "9.0.0"},
#         "os_name": "linux"
#     }
#     mock_get_binaries.return_value = binaries

#     # Mock binary paths
#     loki_path = os.path.join(temp_dir, "loki-linux-amd64")
#     promtail_path = os.path.join(temp_dir, "promtail-linux-amd64")
#     grafana_path = os.path.join(temp_dir, "grafana-server")

#     def get_binary_path_side_effect(name, binaries, base_dir):
#         if name == "loki":
#             return loki_path
#         elif name == "promtail":
#             return promtail_path
#         elif name == "grafana":
#             return grafana_path
#         return None

#     mock_get_binary.side_effect = get_binary_path_side_effect

#     # Mock config files exist
#     def exists_side_effect(path):
#         if path.endswith("lokikit.pid"):
#             return False
#         return True

#     mock_exists.side_effect = exists_side_effect

#     # Mock wait_for_services failing
#     mock_wait.return_value = False

#     # Mock start_process to return a MagicMock with poll method
#     procs = []
#     for _ in range(3):
#         proc_mock = MagicMock()
#         proc_mock.poll.return_value = None  # Process still running
#         procs.append(proc_mock)

#     mock_start.side_effect = procs

#     # Mock logger.error to actually call sys.exit
#     def mock_logger_error(*args, **kwargs):
#         sys.exit(1)

#     mock_logger.error.side_effect = mock_logger_error

#     # Execute start command
#     start_command(ctx, False, False, 20)

#     # Verify we exited with error
#     mock_exit.assert_called_once_with(1)

#     # Verify appropriate error logging
#     mock_logger.error.assert_called()


@patch('lokikit.commands.stop_services')
@patch('lokikit.commands.get_binaries')
@patch('lokikit.commands.get_binary_path')
@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.start_process')
@patch('lokikit.commands.wait_for_services')
@patch('lokikit.commands.read_pid_file')
@patch('os.path.exists')
@patch('os.remove')
@patch('sys.exit')
def test_start_command_with_force(mock_exit, mock_remove, mock_exists, mock_read_pid, mock_wait, mock_start, mock_check,
                                 mock_get_binary, mock_get_binaries,
                                 mock_stop_services, start_test_env):
    """Test start command with --force flag to restart running services."""
    ctx, temp_dir, mock_logger, pid_file = start_test_env

    # Mock existing PID file with running services
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    mock_read_pid.return_value = pids

    # Set force option
    ctx.obj["FORCE"] = True

    # Mock binary information
    binaries = {
        "loki": {"binary": "loki-linux-amd64"},
        "promtail": {"binary": "promtail-linux-amd64"},
        "grafana": {"binary_name": "grafana-server"},
        "os_name": "linux"
    }
    mock_get_binaries.return_value = binaries

    # Mock binary paths
    loki_path = os.path.join(temp_dir, "loki-linux-amd64")
    promtail_path = os.path.join(temp_dir, "promtail-linux-amd64")
    grafana_path = os.path.join(temp_dir, "grafana-server")

    def get_binary_path_side_effect(binary, binaries, base_dir):
        if binary == "loki":
            return loki_path
        elif binary == "promtail":
            return promtail_path
        elif binary == "grafana":
            return grafana_path
        return None

    mock_get_binary.side_effect = get_binary_path_side_effect

    # Mock exists for PID file and config files
    def exists_side_effect(path):
        if path.endswith("lokikit.pid"):
            return True
        return True  # All config files exist

    mock_exists.side_effect = exists_side_effect

    # Mock services already running
    mock_check.return_value = True

    # Mock wait_for_services succeeding
    mock_wait.return_value = True

    # Execute start command with force
    start_command(ctx, False, True, 20)

    # Verify stop_services was called
    mock_stop_services.assert_called_once()

    # Verify PID file was removed
    mock_remove.assert_called_once_with(pid_file)

    # Verify the right processes were started
    assert mock_start.call_count == 3

    # Verify wait_for_services was called
    mock_wait.assert_called_once()

    # Verify appropriate logging
    mock_logger.info.assert_called()


@patch('lokikit.commands.get_binaries')
@patch('lokikit.commands.get_binary_path')
@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.start_process')
@patch('lokikit.commands.ensure_dir')
@patch('lokikit.commands.find_grafana_binary')
@patch('lokikit.commands.read_pid_file')
@patch('os.path.exists')
@patch('sys.exit')
def test_start_missing_configs(mock_exit, mock_exists, mock_read_pid, mock_find_grafana,
                               mock_ensure_dir, mock_start_process, mock_check,
                               mock_get_binary, mock_get_binaries, start_test_env):
    """Test start command when config files are missing."""
    ctx, temp_dir, mock_logger, pid_file = start_test_env

    # Mock no existing PID file
    mock_read_pid.return_value = None

    # Make ensure_dir not raise errors
    mock_ensure_dir.return_value = None

    # Set up the mock_exit to throw an exception we can catch
    def mock_exit_side_effect(code):
        raise SystemExit(code)

    mock_exit.side_effect = mock_exit_side_effect

    # Mock binary information
    binaries = {
        "loki": {"binary": "loki-linux-amd64", "version": "2.5.0"},
        "promtail": {"binary": "promtail-linux-amd64", "version": "2.5.0"},
        "grafana": {"binary_name": "grafana-server", "version": "9.0.0"},
        "os_name": "linux"
    }
    mock_get_binaries.return_value = binaries

    # Mock binary paths
    loki_path = os.path.join(temp_dir, "loki-linux-amd64")
    promtail_path = os.path.join(temp_dir, "promtail-linux-amd64")
    grafana_path = os.path.join(temp_dir, "grafana-server")

    def get_binary_path_side_effect(name, binaries, base_dir):
        # Force this to return None for a binary to cause failure
        return None

    mock_get_binary.side_effect = get_binary_path_side_effect

    # Mock config files don't exist
    mock_exists.return_value = False

    # Mock finding grafana binary
    mock_find_grafana.return_value = None  # This should make binaries check fail

    # Run the command with expected failure
    try:
        start_command(ctx, False, False, 20)
        pytest.fail("Expected SystemExit but no exception was raised")
    except SystemExit as e:
        assert e.code == 1, f"Expected exit code 1, got {e.code}"

    # We should have exited early due to missing binaries
    mock_exit.assert_called_once_with(1)

    # Verify error logging
    assert mock_logger.error.call_count > 0
    assert any("Missing binaries" in str(call) for call in mock_logger.error.call_args_list)


@pytest.fixture
def stop_test_env():
    """Set up test environment for stop command tests."""
    temp_dir = tempfile.mkdtemp()

    # Create mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "HOST": "127.0.0.1",
        "GRAFANA_PORT": 3000,
        "LOKI_PORT": 3100,
        "PROMTAIL_PORT": 9080,
        "CONFIG": {}
    }

    # Setup logger mock
    with patch('lokikit.commands.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        yield ctx, temp_dir, mock_logger

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(temp_dir)


@patch('lokikit.commands.read_pid_file')
@patch('lokikit.commands.stop_services')
@patch('os.path.exists')
@patch('os.remove')
@patch('sys.exit')
def test_stop_command_success(mock_exit, mock_remove, mock_exists, mock_stop, mock_read_pid, stop_test_env):
    """Test stopping services successfully."""
    ctx, temp_dir, mock_logger = stop_test_env

    # Reset all mocks first
    mock_exit.reset_mock()
    mock_exists.reset_mock()
    mock_stop.reset_mock()
    mock_read_pid.reset_mock()
    mock_remove.reset_mock()

    # Mock PIDs file
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    mock_read_pid.return_value = pids

    # Mock successful stop
    mock_stop.return_value = True

    # Mock PID file exists
    mock_exists.return_value = True

    # Run command
    stop_command(ctx, False)

    # Verify stop services was called with PIDs and force=False
    mock_stop.assert_called_once_with(pids, force=False)

    # Verify PID file was removed
    pid_file = os.path.join(temp_dir, "lokikit.pid")
    mock_remove.assert_called_once_with(pid_file)

    # Verify logging
    mock_logger.info.assert_called()


# @patch('lokikit.commands.read_pid_file')
# @patch('lokikit.commands.stop_services')
# @patch('os.path.exists')
# @patch('sys.exit')
# def test_stop_command_failure(mock_read_pid, mock_stop, mock_exists, mock_exit, stop_test_env):
#     """Test handling stop services failure."""
#     ctx, temp_dir, mock_logger = stop_test_env

#     # Reset all mocks to a clean state to avoid side effects from other tests
#     mock_exit.reset_mock()
#     mock_exists.reset_mock()
#     mock_stop.reset_mock()
#     mock_read_pid.reset_mock()

#     # Clearing any previous calls/configuration
#     mock_stop.side_effect = None
#     mock_stop.return_value = False  # This will trigger the error message

#     # Mock PIDs file - use a fresh dict to avoid reference issues
#     pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
#     mock_read_pid.return_value = pids

#     # Mock file doesn't exist so we don't try to remove it
#     mock_exists.return_value = False

#     # Run command
#     stop_command(ctx, False)

#     # Debug - dump the mock call args
#     print("CALL ARGS for each mock:")
#     for name, mock_obj in [("read_pid_file", mock_read_pid), ("stop_services", mock_stop),
#                           ("os.path.exists", mock_exists), ("sys.exit", mock_exit)]:
#         print(f"{name}: {mock_obj.call_args_list}")

#     # Verify stop_services was called
#     mock_stop.assert_called_once()

#     # Check that stop_services is being called with the pids dictionary and force=False
#     mock_stop.assert_called_once_with(pids, force=False)

#     # Verify error logging
#     assert any("Failed to stop one or more services" in str(call) for call in mock_logger.error.call_args_list)


@patch('lokikit.commands.read_pid_file')
@patch('os.path.exists')
@patch('sys.exit')
def test_stop_command_no_pid_file(mock_exit, mock_exists, mock_read_pid, stop_test_env):
    """Test handling when no PID file exists."""
    ctx, temp_dir, mock_logger = stop_test_env

    # Mock no PIDs file
    mock_read_pid.return_value = None

    # Mock no PID file exists
    mock_exists.return_value = False

    # Run command
    stop_command(ctx, False)

    # Verify warning logging
    assert any("No PID file found" in str(call) for call in mock_logger.warning.call_args_list)


@patch('lokikit.commands.read_pid_file')
@patch('lokikit.commands.stop_services')
@patch('os.path.exists')
@patch('os.remove')
@patch('sys.exit')
def test_stop_command_with_force(mock_exit, mock_remove, mock_exists, mock_stop, mock_read_pid, stop_test_env):
    """Test stopping services with force option."""
    ctx, temp_dir, mock_logger = stop_test_env

    # Reset all mocks first
    mock_exit.reset_mock()
    mock_exists.reset_mock()
    mock_stop.reset_mock()
    mock_read_pid.reset_mock()
    mock_remove.reset_mock()

    # Clearing any previous calls/configuration
    mock_stop.side_effect = None
    mock_stop.return_value = True  # Successful stop

    # Mock PIDs file
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    mock_read_pid.return_value = pids

    # Mock PID file exists
    mock_exists.return_value = True

    # Run command with force=True
    stop_command(ctx, True)

    # Test mock_stop was called with the right parameters
    assert mock_stop.call_count == 1, f"Expected stop_services to be called once but was called {mock_stop.call_count} times"

    # Get the actual args that were passed
    args, kwargs = mock_stop.call_args

    # Verify the first argument was our pids dict
    assert args[0] == pids, f"Expected first argument to be {pids}, got {args[0]}"

    # Verify the force parameter was correctly passed
    assert kwargs.get('force') is True, f"Expected force=True, got {kwargs.get('force')}"

    # Verify PID file was removed
    pid_file = os.path.join(temp_dir, "lokikit.pid")
    mock_remove.assert_called_once_with(pid_file)

    # Verify logging
    mock_logger.info.assert_called()


@pytest.fixture
def status_test_env():
    """Set up test environment for status command tests."""
    temp_dir = tempfile.mkdtemp()

    # Create mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "HOST": "127.0.0.1",
        "GRAFANA_PORT": 3000,
        "LOKI_PORT": 3100,
        "PROMTAIL_PORT": 9080,
        "CONFIG": {}
    }

    # Setup logger mock
    with patch('lokikit.commands.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        yield ctx, temp_dir, mock_logger

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(temp_dir)


@patch('lokikit.commands.read_pid_file')
@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.click.echo')
def test_status_all_running(mock_echo, mock_check, mock_read_pid, status_test_env):
    """Test status when all services are running."""
    ctx, temp_dir, mock_logger = status_test_env

    # Mock PIDs file
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    mock_read_pid.return_value = pids

    # Mock services are running
    mock_check.return_value = True

    # Run command
    status_command(ctx)

    # Verify check services was called
    mock_check.assert_called_once_with(pids)

    # Verify logger messages were output
    assert mock_logger.info.call_count >= 3

    # Check "running" in any of the logger.info calls
    any_running = False
    for call_args in mock_logger.info.call_args_list:
        call_str = str(call_args)
        if "running" in call_str.lower():
            any_running = True
            break
    assert any_running


@patch('lokikit.commands.read_pid_file')
@patch('lokikit.commands.check_services_running')
def test_status_not_running(mock_check, mock_read_pid, status_test_env):
    """Test status when services are not running."""
    ctx, temp_dir, mock_logger = status_test_env

    # Mock PIDs file
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    mock_read_pid.return_value = pids

    # Mock services are not running
    mock_check.return_value = False

    # Run command
    status_command(ctx)

    # Verify check services was called
    mock_check.assert_called_once_with(pids)

    # Verify logger.info was called
    mock_logger.info.assert_called()

    # Check "not running" in any of the logger.info calls
    any_not_running = False
    for call_args in mock_logger.info.call_args_list:
        call_str = str(call_args)
        if "no services" in call_str.lower() or "not running" in call_str.lower():
            any_not_running = True
            break
    assert any_not_running


@patch('lokikit.commands.read_pid_file')
def test_status_no_pid_file(mock_read_pid, status_test_env):
    """Test status when no PID file exists."""
    ctx, temp_dir, mock_logger = status_test_env

    # Mock no PIDs file
    mock_read_pid.return_value = None

    # Run command
    status_command(ctx)

    # Verify logger.info was called
    mock_logger.info.assert_called()

    # Check for the actual message used in the code "No services appear to be running"
    any_not_started = False
    for call_args in mock_logger.info.call_args_list:
        call_str = str(call_args)
        if any(msg in call_str.lower() for msg in ["not started", "not running", "no services", "appear"]):
            any_not_started = True
            break
    assert any_not_started


@pytest.fixture
def watch_test_env():
    """Set up test environment for watch command tests."""
    temp_dir = tempfile.mkdtemp()

    # Create mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "CONFIG": {}
    }

    # Setup logger mock
    with patch('lokikit.commands.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        yield ctx, temp_dir, mock_logger

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(temp_dir)


@patch('lokikit.commands.update_promtail_config')
def test_watch_command_success(mock_update, watch_test_env):
    """Test watch command with successful update."""
    ctx, temp_dir, mock_logger = watch_test_env

    # Mock successful config update
    mock_update.return_value = True

    # Run command with basic path
    path = "/var/log/test.log"
    watch_command(ctx, path, None, None)

    # Verify config update was called with correct args
    mock_update.assert_called_once_with(temp_dir, path, None, {})

    # Verify debug logging at minimum
    mock_logger.debug.assert_any_call(f"Adding log path '{path}' with job 'None' to Promtail config...")


@patch('lokikit.commands.update_promtail_config')
def test_watch_command_with_options(mock_update, watch_test_env):
    """Test watch command with job name and labels."""
    ctx, temp_dir, mock_logger = watch_test_env

    # Mock successful config update
    mock_update.return_value = True

    # Run command with job and labels
    path = "/var/log/test.log"
    job = "test_job"
    labels = ["app=test", "env=dev"]

    watch_command(ctx, path, job, labels)

    # Verify config update was called with correct args
    mock_update.assert_called_once()
    args, kwargs = mock_update.call_args
    assert args[0] == temp_dir
    assert args[1] == path
    assert args[2] == job
    # Check labels were parsed into a dict
    labels_dict = args[3]
    assert labels_dict["app"] == "test"
    assert labels_dict["env"] == "dev"

    # Verify debug logging at minimum
    mock_logger.debug.assert_any_call(f"Adding log path '{path}' with job '{job}' to Promtail config...")


@patch('lokikit.commands.update_promtail_config')
def test_watch_command_failure(mock_update, watch_test_env):
    """Test watch command with update failure."""
    ctx, temp_dir, mock_logger = watch_test_env

    # Mock failed config update
    mock_update.return_value = False

    # Run command
    path = "/var/log/test.log"
    watch_command(ctx, path, None, None)

    # Verify config update was called
    mock_update.assert_called_once()

    # Verify logging about no changes
    any_no_changes = False
    for call_args in mock_logger.info.call_args_list:
        if "no changes" in str(call_args).lower():
            any_no_changes = True
            break
    assert any_no_changes


@patch('lokikit.commands.update_promtail_config')
def test_watch_command_invalid_label(mock_update, watch_test_env):
    """Test watch command with invalid label format."""
    ctx, temp_dir, mock_logger = watch_test_env

    # Run command with invalid label
    path = "/var/log/test.log"
    labels = ["invalid-format"]

    # This should not raise an error, but log a warning
    watch_command(ctx, path, None, labels)

    # Verify warning was logged
    any_warning = False
    for call_args in mock_logger.warning.call_args_list:
        if "invalid label format" in str(call_args).lower():
            any_warning = True
            break
    assert any_warning


@pytest.fixture
def clean_test_env():
    """Set up test environment for clean command tests."""
    temp_dir = tempfile.mkdtemp()

    # Create mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "CONFIG": {}
    }

    # Setup logger mock
    with patch('lokikit.commands.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create test files and directories
        os.makedirs(os.path.join(temp_dir, "logs"), exist_ok=True)
        with open(os.path.join(temp_dir, "test-file.txt"), "w") as f:
            f.write("test content")

        yield ctx, temp_dir, mock_logger

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(temp_dir)


@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.read_pid_file')
@patch('shutil.rmtree')
@patch('sys.exit')
def test_clean_command_success(mock_exit, mock_rmtree, mock_read_pid, mock_check, clean_test_env):
    """Test clean command with successful removal."""
    ctx, temp_dir, mock_logger = clean_test_env

    # Mock no running services
    mock_read_pid.return_value = None
    mock_check.return_value = False

    # Run command
    clean_command(ctx)

    # Verify rmtree was called with the base directory
    mock_rmtree.assert_called_once_with(temp_dir)

    # Verify logging
    mock_logger.info.assert_called()


@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.read_pid_file')
@patch('shutil.rmtree')
@patch('sys.exit')
def test_clean_command_services_running(mock_exit, mock_rmtree, mock_read_pid, mock_check, clean_test_env):
    """Test clean command with services still running."""
    ctx, temp_dir, mock_logger = clean_test_env

    # First clear any previous usage of the mocks
    mock_rmtree.reset_mock()
    mock_check.reset_mock()
    mock_exit.reset_mock()

    # Mock running services
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    mock_read_pid.return_value = pids

    # Set the mock to return True BEFORE we call the function
    mock_check.return_value = True

    # Mock the sys.exit to prevent actual exit
    def fake_exit(code):
        raise SystemExit(code)

    mock_exit.side_effect = fake_exit

    # Run command
    try:
        clean_command(ctx)
    except SystemExit:
        pass

    # Verify rmtree was not called - the function should return early
    mock_rmtree.assert_not_called()

    # Verify exit was called with code 1
    mock_exit.assert_called_once_with(1)

    # Verify warning was logged
    assert any("Services are still running" in str(call) for call in mock_logger.warning.call_args_list)


@patch('lokikit.commands.check_services_running')
@patch('lokikit.commands.read_pid_file')
@patch('shutil.rmtree')
@patch('os.path.exists')
@patch('sys.exit')
def test_clean_command_removal_error(mock_exit, mock_exists, mock_rmtree, mock_read_pid, mock_check, clean_test_env):
    """Test clean command with directory removal error."""
    ctx, temp_dir, mock_logger = clean_test_env

    # Mock no running services
    mock_read_pid.return_value = None
    mock_check.return_value = False

    # Mock directory exists
    mock_exists.return_value = True

    # Mock removal error
    mock_rmtree.side_effect = OSError("Permission denied")

    # Mock the sys.exit to prevent actual exit
    def fake_exit(code):
        raise SystemExit(code)

    mock_exit.side_effect = fake_exit

    # Run command
    try:
        clean_command(ctx)
    except SystemExit:
        pass

    # Verify error was logged and sys.exit was called
    mock_logger.error.assert_called()
    mock_exit.assert_called_once_with(1)


@pytest.fixture
def force_quit_test_env():
    """Set up test environment for force-quit command tests."""
    temp_dir = tempfile.mkdtemp()

    # Create mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "CONFIG": {}
    }

    # Setup logger mock
    with patch('lokikit.commands.get_logger') as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create test PID file
        pid_file = os.path.join(temp_dir, "lokikit.pid")
        with open(pid_file, "w") as f:
            f.write("loki=1000\npromtail=2000\ngrafana=3000\n")

        yield ctx, temp_dir, mock_logger, pid_file

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(temp_dir)


@patch('subprocess.run')
@patch('os.path.exists')
@patch('os.remove')
@patch('sys.exit')
def test_force_quit_command_success(mock_exit, mock_remove, mock_exists, mock_run, force_quit_test_env):
    """Test force-quit command with successful termination."""
    ctx, temp_dir, mock_logger, pid_file = force_quit_test_env

    # Mock PID file exists
    mock_exists.return_value = True

    # Mock successful subprocess calls
    mock_run.return_value = MagicMock(returncode=0, stdout="1000 2000 3000")

    # Run command
    force_quit_command(ctx)

    # Verify subprocess was called for all processes
    assert mock_run.call_count >= 2  # At least pgrep and kill

    # Verify PID file was removed
    mock_remove.assert_called_once_with(pid_file)

    # Verify logging
    mock_logger.info.assert_called()


@patch('subprocess.run')
@patch('os.path.exists')
@patch('sys.exit')
def test_force_quit_command_no_processes(mock_exit, mock_exists, mock_run, force_quit_test_env):
    """Test force-quit command with no running processes."""
    ctx, temp_dir, mock_logger, pid_file = force_quit_test_env

    # Mock PID file doesn't exist
    mock_exists.return_value = False

    # Mock empty subprocess output (no processes found)
    mock_run.return_value = MagicMock(returncode=1, stdout="")

    # Run command
    force_quit_command(ctx)

    # Verify subprocess was called for pgrep
    mock_run.assert_called()

    # Verify info logging
    mock_logger.info.assert_called()


@patch('subprocess.run')
@patch('os.path.exists')
@patch('os.remove')
@patch('sys.exit')
def test_force_quit_command_kill_error(mock_exit, mock_remove, mock_exists, mock_run, force_quit_test_env):
    """Test force-quit command with kill command error."""
    ctx, temp_dir, mock_logger, pid_file = force_quit_test_env

    # Mock PID file exists
    mock_exists.return_value = True

    # Mock successful pgrep but failed kill
    def mock_run_side_effect(*args, **kwargs):
        if args[0][0] == "pgrep":
            return MagicMock(returncode=0, stdout="1000 2000 3000")
        elif args[0][0] == "kill":
            return MagicMock(returncode=1, stderr="Operation not permitted")
        return MagicMock(returncode=0, stdout="")

    mock_run.side_effect = mock_run_side_effect

    # Run command
    force_quit_command(ctx)

    # PID file should still be removed even if kill fails
    mock_remove.assert_called_once_with(pid_file)

    # Verify error logging
    mock_logger.error.assert_called()
