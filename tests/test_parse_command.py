"""Tests for the parse command in lokikit."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from lokikit.commands import parse_command


@pytest.fixture
def parse_test_env():
    """Set up test environment for parse command tests."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    # Create a mock context
    ctx = MagicMock()
    ctx.obj = {
        "BASE_DIR": temp_dir,
        "HOST": "127.0.0.1",
        "GRAFANA_PORT": 3000,
        "LOKI_PORT": 3100,
        "PROMTAIL_PORT": 9080,
        "CONFIG": {},
    }

    # Create a test logs directory
    logs_dir = os.path.join(temp_dir, "test_logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Create some test log files
    log_files = {
        "app.log": [
            "2023-10-15T10:00:00 INFO Starting application",
            "2023-10-15T10:01:00 ERROR Connection failed",
        ],
        "json_logs.log": [
            json.dumps(
                {
                    "timestamp": "2023-10-15T10:00:00",
                    "level": "INFO",
                    "message": "Server started",
                    "host": "example.com",
                }
            ),
            json.dumps(
                {"timestamp": "2023-10-15T10:01:00", "level": "ERROR", "message": "Connection timeout", "status": 500}
            ),
            json.dumps(
                {"timestamp": "2023-10-15T10:02:00", "level": "INFO", "message": "Connection restored", "status": 200}
            ),
        ],
    }

    for filename, lines in log_files.items():
        with open(os.path.join(logs_dir, filename), "w") as f:
            f.write("\n".join(lines))

    # Setup logger mock
    logger_mock = MagicMock()

    yield ctx, temp_dir, logs_dir, logger_mock

    # Clean up after tests
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for directory in dirs:
            os.rmdir(os.path.join(root, directory))
    os.rmdir(temp_dir)


@patch("lokikit.commands.get_logger")
@patch("lokikit.commands.check_services_running")
@patch("lokikit.commands.watch_command")
@patch("lokikit.commands.create_dashboard")
@patch("lokikit.commands.save_dashboard")
@patch("lokikit.commands.Console")
@patch("lokikit.commands.Prompt.ask")
@patch("lokikit.commands.Confirm.ask")
@patch("lokikit.commands.Progress")
def test_parse_command_directory_exists(
    mock_progress_class,
    mock_confirm,
    mock_prompt,
    mock_console_class,
    mock_save_dashboard,
    mock_create_dashboard,
    mock_watch_command,
    mock_check_services,
    mock_get_logger,
    parse_test_env,
):
    """Test parse command when directory exists."""
    ctx, temp_dir, logs_dir, logger_mock = parse_test_env

    # Mock the logger
    mock_get_logger.return_value = logger_mock

    # Mock the service status check
    mock_check_services.return_value = {
        "grafana": {"running": True},
        "promtail": {"running": True},
    }

    # Mock the Console
    mock_console = MagicMock()
    mock_console_class.return_value = mock_console

    # Mock Progress
    mock_progress = MagicMock()
    mock_progress_class.return_value.__enter__.return_value = mock_progress
    mock_progress.add_task.return_value = 0

    # Set up return values for prompts
    mock_prompt.side_effect = [
        "timestamp,level,message",  # fields to include
        "test_job",  # job name
        "Test Dashboard",  # dashboard name
    ]

    # Set up confirm prompt
    mock_confirm.return_value = False  # No custom labels

    # Mock the dashboard creation
    mock_dashboard = {
        "uid": "test123",
        "title": "Test Dashboard",
        "panels": [{"id": 1, "type": "logs"}, {"id": 2, "type": "table"}],
    }
    mock_create_dashboard.return_value = mock_dashboard

    # Mock the dashboard saving
    dashboard_path = os.path.join(temp_dir, "dashboards", "test_dashboard.json")
    mock_save_dashboard.return_value = dashboard_path

    # Call the function
    parse_command(ctx, logs_dir, "Test Dashboard", 5, 100)

    # No need to verify specific logger calls as they might vary

    # Verify service status was checked
    mock_check_services.assert_called_once_with(temp_dir)

    # Verify proper prompts were shown
    assert mock_prompt.call_count == 2  # When dashboard name is provided, only need job name and fields

    # Verify dashboard was created with correct parameters
    mock_create_dashboard.assert_called_once()
    _, kwargs = mock_create_dashboard.call_args
    assert kwargs["dashboard_name"] == "Test Dashboard"
    assert "timestamp" in kwargs["fields"]
    assert "level" in kwargs["fields"]
    assert "message" in kwargs["fields"]
    assert kwargs["job_name"] == "test_job"

    # Verify dashboard was saved
    mock_save_dashboard.assert_called_once_with(mock_dashboard, temp_dir, "Test Dashboard")

    # Verify promtail config was updated
    mock_watch_command.assert_called_once()


@patch("lokikit.commands.get_logger")
@patch("lokikit.commands.Console")
def test_parse_command_directory_does_not_exist(
    mock_console_class,
    mock_get_logger,
    parse_test_env,
):
    """Test parse command when directory does not exist."""
    ctx, temp_dir, _, logger_mock = parse_test_env

    # Mock the logger
    mock_get_logger.return_value = logger_mock

    # Mock the Console
    mock_console = MagicMock()
    mock_console_class.return_value = mock_console

    # Call the function with a non-existent directory
    non_existent_dir = os.path.join(temp_dir, "non_existent")
    parse_command(ctx, non_existent_dir)

    # Verify error was logged
    logger_mock.error.assert_called_once()
    assert "does not exist" in logger_mock.error.call_args[0][0]

    # Verify error was printed
    mock_console.print.assert_called_once()
    args, _ = mock_console.print.call_args
    assert "does not exist" in args[0]


@patch("lokikit.commands.get_logger")
@patch("lokikit.commands.check_services_running")
@patch("lokikit.commands.watch_command")
@patch("lokikit.commands.create_dashboard")
@patch("lokikit.commands.save_dashboard")
@patch("lokikit.commands.Console")
@patch("lokikit.commands.Prompt.ask")
@patch("lokikit.commands.Confirm.ask")
@patch("lokikit.commands.Progress")
def test_parse_command_json_fields_detection(
    mock_progress_class,
    mock_confirm,
    mock_prompt,
    mock_console_class,
    mock_save_dashboard,
    mock_create_dashboard,
    mock_watch_command,
    mock_check_services,
    mock_get_logger,
    parse_test_env,
):
    """Test parse command correctly detects JSON fields."""
    ctx, temp_dir, logs_dir, logger_mock = parse_test_env

    # Mock the logger
    mock_get_logger.return_value = logger_mock

    # Mock the service status check
    mock_check_services.return_value = {
        "grafana": {"running": False},
        "promtail": {"running": False},
    }

    # Mock the Console
    mock_console = MagicMock()
    mock_console_class.return_value = mock_console

    # Mock Progress
    mock_progress = MagicMock()
    mock_progress_class.return_value.__enter__.return_value = mock_progress
    mock_progress.add_task.return_value = 0

    # Set up return values for prompts
    mock_prompt.side_effect = [
        "all",  # fields to include (all)
        "json_logs",  # job name
        "JSON Logs Dashboard",  # dashboard name
    ]

    # Set up confirm prompt
    mock_confirm.return_value = False  # No custom labels

    # Mock the dashboard creation
    mock_dashboard = {
        "uid": "test456",
        "title": "JSON Logs Dashboard",
        "panels": [{"id": 1, "type": "logs"}, {"id": 2, "type": "table"}],
    }
    mock_create_dashboard.return_value = mock_dashboard

    # Mock the dashboard saving
    dashboard_path = os.path.join(temp_dir, "dashboards", "json_logs_dashboard.json")
    mock_save_dashboard.return_value = dashboard_path

    # Call the function
    parse_command(ctx, logs_dir)

    # No need to verify specific logger calls as they might vary

    # Verify service status was checked
    mock_check_services.assert_called_once_with(temp_dir)

    # Verify dashboard was created with correct fields
    mock_create_dashboard.assert_called_once()
    _, kwargs = mock_create_dashboard.call_args

    # Should include all detected fields from the JSON logs
    assert "timestamp" in kwargs["fields"]
    assert "level" in kwargs["fields"]
    assert "message" in kwargs["fields"]
    assert "host" in kwargs["fields"]
    assert "status" in kwargs["fields"]

    # Verify dashboard was saved
    mock_save_dashboard.assert_called_once_with(mock_dashboard, temp_dir, "JSON Logs Dashboard")

    # Verify restart instructions were shown for non-running services
    messages = [args[0] for args, _ in mock_console.print.call_args_list]
    assert any("Start Lokikit services" in str(m) for m in messages)
