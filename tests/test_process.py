"""Tests for the LokiKit process module."""

import os
import signal
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from lokikit.process import (
    check_services_running,
    read_pid_file,
    service_is_accessible,
    start_process,
    stop_services,
    wait_for_services,
    write_pid_file,
)


@pytest.fixture
def temp_setup():
    """Set up test environment."""
    temp_dir = tempfile.mkdtemp()
    log_file = os.path.join(temp_dir, "test.log")

    yield temp_dir, log_file

    # Cleanup
    if os.path.exists(log_file):
        os.remove(log_file)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)


@pytest.fixture
def mock_logger():
    """Set up logger mock."""
    with patch("lokikit.process.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger


@patch("subprocess.Popen")
def test_start_process(mock_popen, temp_setup, mock_logger):
    """Test starting a process."""
    temp_dir, log_file = temp_setup
    mock_process = MagicMock()
    mock_popen.return_value = mock_process

    cmd = ["test", "command"]
    process = start_process(cmd, log_file)

    # Check process was started with correct args
    mock_popen.assert_called_once()
    assert process == mock_process
    mock_logger.info.assert_called_once()


def test_write_pid_file(temp_setup, mock_logger):
    """Test writing PIDs to a file."""
    temp_dir, _ = temp_setup
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}

    pid_file = write_pid_file(pids, temp_dir)

    # Check file exists and contains correct PIDs
    assert os.path.exists(pid_file)

    with open(pid_file) as f:
        content = f.read()

    for name, pid in pids.items():
        assert f"{name}={pid}" in content

    mock_logger.debug.assert_called_once()

    # Clean up
    os.remove(pid_file)


def test_read_pid_file_success(temp_setup):
    """Test reading PIDs from a file."""
    temp_dir, _ = temp_setup
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    pid_file = os.path.join(temp_dir, "lokikit.pid")

    with open(pid_file, "w") as f:
        for name, pid in pids.items():
            f.write(f"{name}={pid}\n")

    read_pids = read_pid_file(temp_dir)

    assert read_pids == pids

    # Clean up
    os.remove(pid_file)


def test_read_pid_file_nonexistent(temp_setup):
    """Test reading from a nonexistent PID file."""
    temp_dir, _ = temp_setup
    read_pids = read_pid_file(temp_dir)
    assert read_pids is None


def test_read_pid_file_invalid(temp_setup):
    """Test reading from an invalid PID file."""
    temp_dir, _ = temp_setup
    pid_file = os.path.join(temp_dir, "lokikit.pid")

    with open(pid_file, "w") as f:
        f.write("invalid=content\n")
        f.write("loki=invalid\n")
        f.write("promtail=2000\n")

    read_pids = read_pid_file(temp_dir)

    # Should only include the valid line
    assert read_pids == {"promtail": 2000}

    # Clean up
    os.remove(pid_file)


@patch("os.kill")
@patch("subprocess.run")
def test_check_services_running_all_running(mock_run, mock_kill):
    """Test checking all services running by PID."""
    # All services are running (os.kill doesn't raise exception)
    mock_kill.return_value = None

    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    result = check_services_running(pids)

    assert result is True
    # Should have called kill 3 times with signal 0
    assert mock_kill.call_count == 3
    mock_run.assert_not_called()  # Shouldn't need to use pgrep


@patch("os.kill")
@patch("subprocess.run")
def test_check_services_running_none_running(mock_run, mock_kill):
    """Test checking when no services are running."""
    # No services are running (os.kill raises OSError)
    mock_kill.side_effect = OSError()

    # pgrep also fails
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""

    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    result = check_services_running(pids)

    assert result is False
    assert mock_kill.call_count == 3
    assert mock_run.call_count == 3  # Should try pgrep for each service


@patch("os.kill")
@patch("subprocess.run")
def test_check_services_running_some_found_by_pattern(mock_run, mock_kill):
    """Test finding services by pattern when PIDs have changed."""
    # All services fail by PID but some found by pattern
    mock_kill.side_effect = OSError()

    # Only loki found by pattern
    def mock_run_side_effect(*args, **kwargs):
        result = MagicMock()
        if "loki" in args[0][2]:
            result.returncode = 0
            result.stdout = "1500\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    mock_run.side_effect = mock_run_side_effect

    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}
    result = check_services_running(pids)

    assert result is False  # Not all services running
    assert mock_kill.call_count == 3
    assert mock_run.call_count == 3

    # Check that pids dict was updated with new PID for loki
    assert pids["loki"] == 1500


@patch("socket.socket")
def test_service_is_accessible_success(mock_socket):
    """Test checking if a service is accessible."""
    # Set up mock for socket connection success
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance

    result = service_is_accessible("localhost", 3000)

    assert result is True
    mock_socket_instance.connect.assert_called_once_with(("localhost", 3000))
    mock_socket_instance.close.assert_called_once()


@patch("socket.socket")
def test_service_is_accessible_failure(mock_socket):
    """Test checking if a service is not accessible."""
    # Set up mock for socket connection failure
    mock_socket_instance = MagicMock()
    mock_socket_instance.connect.side_effect = OSError()
    mock_socket.return_value = mock_socket_instance

    result = service_is_accessible("localhost", 3000)

    assert result is False
    mock_socket_instance.close.assert_called_once()


@patch("lokikit.process.service_is_accessible")
@patch("time.sleep")
def test_wait_for_services_success(mock_sleep, mock_is_accessible, mock_logger):
    """Test waiting for services to be accessible."""
    # First call returns False, second call returns True
    mock_is_accessible.side_effect = [False, True]

    host = "localhost"
    ports = {"grafana": 3000}
    process = MagicMock()
    process.poll.return_value = None
    procs = {"grafana": process}

    result = wait_for_services(host, ports, procs, timeout=2)

    assert result is True
    assert mock_is_accessible.call_count >= 1
    mock_sleep.assert_called()
    process.poll.assert_called()


@patch("lokikit.process.service_is_accessible")
@patch("time.sleep")
def test_wait_for_services_timeout(mock_sleep, mock_is_accessible, mock_logger):
    """Test timeout while waiting for services."""
    # Service never becomes accessible
    mock_is_accessible.return_value = False

    host = "localhost"
    ports = {"grafana": 3000}
    process = MagicMock()
    process.poll.return_value = None
    procs = {"grafana": process}

    result = wait_for_services(host, ports, procs, timeout=1)

    assert result is False
    assert mock_is_accessible.call_count > 0
    assert mock_sleep.call_count > 0
    process.poll.assert_called()


@patch("lokikit.process.service_is_accessible")
def test_wait_for_services_process_terminated(mock_is_accessible, mock_logger):
    """Test early return if process terminates while waiting."""
    mock_is_accessible.return_value = False

    host = "localhost"
    ports = {"grafana": 3000}
    process = MagicMock()

    # Set up a side effect list that can be consumed multiple times
    # Return None first time, then 1 (error code)
    process.poll.side_effect = [
        None,
        1,
        None,
        1,
    ]  # Double the values to handle possible multiple calls

    procs = {"grafana": process}

    result = wait_for_services(host, ports, procs, timeout=5)

    # Should return False since process terminated with non-zero code
    assert result is False


@patch("lokikit.process.service_is_accessible")
def test_wait_for_services_0_0_0_0(mock_is_accessible, mock_logger):
    """Test behavior when host is 0.0.0.0."""
    mock_is_accessible.return_value = True

    host = "0.0.0.0"  # Special case: should use 127.0.0.1 for checks
    ports = {"grafana": 3000}
    process = MagicMock()
    process.poll.return_value = None
    procs = {"grafana": process}

    result = wait_for_services(host, ports, procs, timeout=1)

    assert result is True
    mock_is_accessible.assert_called_with("127.0.0.1", 3000)


@patch("os.kill")
@patch("time.sleep")
def test_stop_services_success(mock_sleep, mock_kill, mock_logger):
    """Test stopping services normally."""
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}

    # Create a detailed sequence of side effects for all three services
    # The pattern needed is:
    # - SIGTERM success for each service
    # - Then signal 0 checks should raise OSError (process gone) after SIGTERM

    kill_effects = []

    # For each service:
    for _pid in [1000, 2000, 3000]:
        # SIGTERM call (success)
        kill_effects.append(None)
        # First signal 0 check should raise OSError (process terminated by SIGTERM)
        kill_effects.append(OSError())

    # Add extra effects in case the implementation makes more checks
    kill_effects.extend([OSError()] * 10)

    mock_kill.side_effect = kill_effects

    stop_services(pids)

    # Should have been called at least 6 times (SIGTERM + check for each of 3 services)
    assert mock_kill.call_count >= 6

    # Verify each service got SIGTERM
    mock_kill.assert_any_call(1000, signal.SIGTERM)
    mock_kill.assert_any_call(2000, signal.SIGTERM)
    mock_kill.assert_any_call(3000, signal.SIGTERM)


@patch("os.kill")
@patch("time.sleep")
def test_stop_services_requires_sigkill(mock_sleep, mock_kill, mock_logger):
    """Test stopping services that require SIGKILL."""
    pids = {"loki": 1000}

    # Define a more detailed sequence of mock behaviors:
    # 1. SIGTERM (pid 1000) -> None (success)
    # 2-20+. Check if running (pid 1000, signal 0) -> None (still running)
    # 21. SIGKILL (pid 1000) -> None (success)
    # 22-30+. Check if running after SIGKILL (pid 1000, signal 0) -> OSError (gone)

    kill_effects = []
    # Add SIGTERM effect
    kill_effects.append(None)
    # Add 20 checks for running after SIGTERM (all return None - still running)
    kill_effects.extend([None] * 20)
    # Add SIGKILL effect
    kill_effects.append(None)
    # Add 10 checks for running after SIGKILL - last one returns OSError (process gone)
    kill_effects.extend([None] * 9 + [OSError()])

    mock_kill.side_effect = kill_effects

    stop_services(pids)

    # Should have calls for SIGTERM, checking, SIGKILL, and checking again
    # The actual number may vary depending on the implementation, but it should be at least:
    # 1 (SIGTERM) + 20 (checks) + 1 (SIGKILL) + 1 (final check) = 23 minimum
    assert mock_kill.call_count >= 23


@patch("os.kill")
@patch("time.sleep")
def test_stop_services_sigkill_fails(mock_sleep, mock_kill, mock_logger):
    """Test when both SIGTERM and SIGKILL fail."""
    pids = {"loki": 1000}

    # Define side effect sequence - providing more than enough effects for all possible checks
    kill_effects = []
    # Add SIGTERM effect
    kill_effects.append(None)
    # Add 20 checks for running after SIGTERM (all return None - still running)
    kill_effects.extend([None] * 20)
    # Add SIGKILL effect that raises an error
    kill_effects.append(OSError())

    mock_kill.side_effect = kill_effects

    stop_services(pids)

    # Should have calls for SIGTERM, checking multiple times, then SIGKILL attempt
    # Actual count may vary with implementation
    # 1 (SIGTERM) + 20 (checks) + 1 (SIGKILL attempt) = 22 minimum
    assert mock_kill.call_count >= 22


@patch("os.kill")
def test_stop_services_not_running(mock_kill, mock_logger):
    """Test stopping services that aren't running."""
    pids = {"loki": 1000, "promtail": 2000, "grafana": 3000}

    # All processes are already gone
    mock_kill.side_effect = OSError()

    stop_services(pids)

    # Should still try to kill each service once
    assert mock_kill.call_count == 3


@patch("os.kill")
@patch("time.sleep")
def test_stop_services_permission_error(mock_sleep, mock_kill, mock_logger):
    """Test permission error when stopping services."""
    pids = {"loki": 1000}

    # Permission error
    mock_kill.side_effect = PermissionError()

    stop_services(pids)

    # Should have tried once
    assert mock_kill.call_count == 1
    mock_logger.error.assert_called()
