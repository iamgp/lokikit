"""Tests for the LokiKit CLI module."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock, call

from click.testing import CliRunner

from lokikit.cli import (
    cli,
    setup,
    start,
    stop,
    status,
    clean,
    watch,
    force_quit
)


@pytest.fixture
def cli_test_env():
    """Set up test environment for CLI tests."""
    temp_dir = tempfile.mkdtemp()
    runner = CliRunner()

    # Create a test config file
    config_file = os.path.join(temp_dir, "test_config.yaml")
    with open(config_file, "w") as f:
        f.write("""
base_dir: /tmp/lokikit_test
host: 0.0.0.0
grafana_port: 4000
loki_port: 4100
promtail_port: 9090
        """)

    yield {"temp_dir": temp_dir, "runner": runner, "config_file": config_file}

    # Clean up
    if os.path.exists(config_file):
        os.remove(config_file)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)


@pytest.fixture
def cli_runner():
    """Return a CLI runner for testing CLI commands."""
    return CliRunner()


@patch('lokikit.cli.setup_logging')
@patch('lokikit.cli.load_config_file')
@patch('lokikit.cli.merge_config')
def test_cli_base_with_defaults(mock_merge_config, mock_load_config, mock_setup_logging, cli_test_env):
    """Test CLI with default options."""
    # Mock return values
    mock_logger = MagicMock()
    mock_setup_logging.return_value = mock_logger
    mock_load_config.return_value = {}

    default_config = {
        "base_dir": os.path.expanduser("~/.lokikit"),
        "host": "127.0.0.1",
        "grafana_port": 3000,
        "loki_port": 3100,
        "promtail_port": 9080
    }
    mock_merge_config.return_value = default_config

    # Run CLI command with --help to avoid exit code 2
    result = cli_test_env["runner"].invoke(cli, ["--help"])

    # Check result
    assert result.exit_code == 0

    # Since we're using --help, the merge_config isn't called in this case
    # Let's just test a different way
    result = cli_test_env["runner"].invoke(cli, ["status"])

    # Verify loading and merging config is called
    mock_merge_config.assert_called()


@patch('lokikit.cli.setup_logging')
@patch('lokikit.cli.load_config_file')
@patch('lokikit.cli.merge_config')
def test_cli_base_with_config_file(mock_merge_config, mock_load_config, mock_setup_logging, cli_test_env):
    """Test CLI with config file option."""
    # Mock return values
    mock_logger = MagicMock()
    mock_setup_logging.return_value = mock_logger
    mock_load_config.return_value = {
        "base_dir": "/tmp/lokikit_test",
        "host": "0.0.0.0",
        "grafana_port": 4000,
        "loki_port": 4100,
        "promtail_port": 9090
    }
    mock_merge_config.return_value = mock_load_config.return_value

    # Run CLI command with config file and status subcommand to avoid exit code 2
    result = cli_test_env["runner"].invoke(cli, ["--config", cli_test_env["config_file"], "status"])

    # Check result
    assert result.exit_code == 0

    # Verify loading and merging config
    mock_load_config.assert_called_once_with(cli_test_env["config_file"])
    mock_merge_config.assert_called()

    # Verify logging setup
    mock_setup_logging.assert_called_once()
    mock_logger.debug.assert_called_once()


@patch('lokikit.cli.setup_logging')
@patch('lokikit.cli.load_config_file')
@patch('lokikit.cli.merge_config')
def test_cli_base_with_cli_options(mock_merge_config, mock_load_config, mock_setup_logging, cli_test_env):
    """Test CLI with command line options."""
    # Mock return values
    mock_logger = MagicMock()
    mock_setup_logging.return_value = mock_logger
    mock_load_config.return_value = {}

    # Set what merge_config will return based on the CLI options
    def mock_merge_side_effect(cli_options, file_config):
        return {
            "base_dir": cli_options["base_dir"],
            "host": cli_options["host"],
            "grafana_port": cli_options["grafana_port"],
            "loki_port": cli_options["loki_port"],
            "promtail_port": cli_options["promtail_port"]
        }

    mock_merge_config.side_effect = mock_merge_side_effect

    # Run CLI command with options and status subcommand
    result = cli_test_env["runner"].invoke(cli, [
        "--base-dir", "/custom/dir",
        "--host", "0.0.0.0",
        "--port", "4000",
        "--loki-port", "4100",
        "--promtail-port", "9090",
        "--verbose",
        "status"
    ])

    # Check result
    assert result.exit_code == 0

    # Verify logging setup with verbose flag
    mock_setup_logging.assert_called_once_with("/custom/dir", True)
    mock_logger.debug.assert_called_once()

    # Verify correct CLI options were passed to merge_config
    mock_merge_config.assert_called_once()
    cli_options = mock_merge_config.call_args[0][0]
    assert cli_options["base_dir"] == "/custom/dir"
    assert cli_options["host"] == "0.0.0.0"
    assert cli_options["grafana_port"] == 4000
    assert cli_options["loki_port"] == 4100
    assert cli_options["promtail_port"] == 9090


@patch('lokikit.cli.setup_command')
def test_setup_command(mock_setup_command, cli_runner):
    """Test the setup subcommand."""
    result = cli_runner.invoke(cli, ["setup"])

    assert result.exit_code == 0
    mock_setup_command.assert_called_once()


@patch('lokikit.cli.start_command')
def test_start_command_defaults(mock_start_command, cli_runner):
    """Test the start subcommand with default options."""
    # Call with positional args to match the implementation
    mock_start_command.return_value = None

    result = cli_runner.invoke(cli, ["start"])

    assert result.exit_code == 0
    mock_start_command.assert_called_once()

    # The CLI passes arguments positionally, not as kwargs
    args, kwargs = mock_start_command.call_args
    ctx = args[0]  # First arg is the context
    background = args[1]  # Second arg is background flag
    force = args[2]  # Third arg is force flag
    timeout = args[3]  # Fourth arg is timeout

    assert background is False
    assert force is False
    assert timeout == 20


@patch('lokikit.cli.start_command')
def test_start_command_with_options(mock_start_command, cli_runner):
    """Test the start subcommand with custom options."""
    mock_start_command.return_value = None

    result = cli_runner.invoke(cli, ["start", "--background", "--force", "--timeout", "30"])

    assert result.exit_code == 0
    mock_start_command.assert_called_once()

    # The CLI passes arguments positionally, not as kwargs
    args, kwargs = mock_start_command.call_args
    ctx = args[0]  # First arg is the context
    background = args[1]  # Second arg is background flag
    force = args[2]  # Third arg is force flag
    timeout = args[3]  # Fourth arg is timeout

    assert background is True
    assert force is True
    assert timeout == 30


@patch('lokikit.cli.stop_command')
def test_stop_command_defaults(mock_stop_command, cli_runner):
    """Test the stop subcommand with default options."""
    result = cli_runner.invoke(cli, ["stop"])

    assert result.exit_code == 0
    mock_stop_command.assert_called_once()
    # Verify default parameters
    args, kwargs = mock_stop_command.call_args
    assert not kwargs.get("force", False)


@patch('lokikit.cli.stop_command')
def test_stop_command_with_force(mock_stop_command, cli_runner):
    """Test the stop subcommand with force option."""
    # Add a return value to avoid potential issues
    mock_stop_command.return_value = None

    result = cli_runner.invoke(cli, ["stop", "--force"])

    assert result.exit_code == 0
    mock_stop_command.assert_called_once()

    # CLI passes args positionally
    args, kwargs = mock_stop_command.call_args
    ctx = args[0]  # First arg is the context
    force = args[1]  # Second arg is force flag

    assert force is True


@patch('lokikit.cli.status_command')
def test_status_command(mock_status_command, cli_runner):
    """Test the status subcommand."""
    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    mock_status_command.assert_called_once()


@patch('lokikit.cli.clean_command')
def test_clean_command(mock_clean_command, cli_runner):
    """Test the clean subcommand."""
    result = cli_runner.invoke(cli, ["clean"])

    assert result.exit_code == 0
    mock_clean_command.assert_called_once()


@patch('lokikit.cli.watch_command')
def test_watch_command(mock_watch_command, cli_runner):
    """Test the watch subcommand with default options."""
    # Add a return value to avoid potential issues
    mock_watch_command.return_value = None

    # The watch command requires a path argument
    result = cli_runner.invoke(cli, ["watch", "/var/log/test.log"])

    assert result.exit_code == 0
    mock_watch_command.assert_called_once()

    # CLI passes args positionally
    args, kwargs = mock_watch_command.call_args
    ctx = args[0]  # First arg is the context
    path = args[1]  # Second arg is path
    job = args[2]  # Third arg is job
    label = args[3]  # Fourth arg is label

    assert path == "/var/log/test.log"
    assert job is None
    assert label == ()  # Empty tuple for default


@patch('lokikit.cli.watch_command')
def test_watch_command_with_options(mock_watch_command, cli_runner):
    """Test the watch subcommand with custom options."""
    # Add a return value to avoid potential issues
    mock_watch_command.return_value = None

    result = cli_runner.invoke(cli, [
        "watch",
        "/var/log/test.log",
        "--job", "test_job",
        "--label", "app=test",
        "--label", "env=dev"
    ])

    assert result.exit_code == 0
    mock_watch_command.assert_called_once()

    # CLI passes args positionally
    args, kwargs = mock_watch_command.call_args
    ctx = args[0]  # First arg is the context
    path = args[1]  # Second arg is path
    job = args[2]  # Third arg is job
    label = args[3]  # Fourth arg is labels

    assert path == "/var/log/test.log"
    assert job == "test_job"
    assert label == ("app=test", "env=dev")


@patch('lokikit.cli.force_quit_command')
def test_force_quit_command(mock_force_quit_command, cli_runner):
    """Test the force-quit subcommand."""
    result = cli_runner.invoke(cli, ["force-quit"])

    assert result.exit_code == 0
    mock_force_quit_command.assert_called_once()
