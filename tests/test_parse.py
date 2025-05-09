"""Tests for the parse command in lokikit/lokikit/commands.py."""

import json
import os

import pytest
import yaml
from click.testing import CliRunner

from lokikit.cli import cli

# Sample log lines based on the provided example (Loguru JSON format)
# Ensure valid JSON (double quotes internally) and each log is a single line.
SAMPLE_LOG_1 = '{"text": "2025-04-25 23:02:19 | DEBUG    | Creating Plate from config string | {\\"module\\": \\"plates\\", \\"method\\": \\"new\\", \\"assay_id\\": \\"plate1\\"}", "record": {"elapsed": {"repr": "0:00:02.132", "seconds": 2.132}, "exception": null, "extra": {"module": "plates", "method": "new", "assay_id": "plate1", "params": ["p1", "p2"]}, "file": {"name": "logging.py", "path": "/path/to/logging.py"}, "function": "debug", "level": {"icon": "🐞", "name": "DEBUG", "no": 10}, "line": 80, "message": "Creating Plate from config string", "module": "logging", "name": "my_logger", "process": {"id": 123, "name": "MainProcess"}, "thread": {"id": 456, "name": "MainThread"}, "time": {"repr": "2025-04-25 23:02:19.884+00:00", "timestamp": 1745622139.884}}}'
SAMPLE_LOG_2 = '{"text": "2025-04-25 23:02:19 | INFO     | Loading assay config: success | {\\"app\\": \\"pipeline\\", \\"config_path\\": \\"cfg.yaml\\"}", "record": {"elapsed": {"repr": "0:00:02.206", "seconds": 2.206}, "exception": null, "extra": {"app": "pipeline", "config_path": "cfg.yaml", "status": {"code": 200, "details": "OK"}}, "file": {"name": "config.py", "path": "/path/to/config.py"}, "function": "info", "level": {"icon": "ℹ️", "name": "INFO", "no": 20}, "line": 100, "message": "Loading assay config: success", "module": "config", "name": "my_logger", "process": {"id": 123, "name": "MainProcess"}, "thread": {"id": 456, "name": "MainThread"}, "time": {"repr": "2025-04-25 23:02:19.958+00:00", "timestamp": 1745622139.958}}}'
SAMPLE_LOG_3 = '{"text": "2025-04-25 23:02:19 | WARNING  | File not found | {\\"app\\": \\"pipeline\\", \\"filename\\": \\"data.csv\\"}", "record": {"elapsed": {"repr": "0:00:02.214", "seconds": 2.214}, "exception": null, "extra": {"app": "pipeline", "filename": "data.csv"}, "file": {"name": "loader.py", "path": "/path/to/loader.py"}, "function": "warning", "level": {"icon": "⚠️", "name": "WARNING", "no": 30}, "line": 50, "message": "File not found", "module": "loader", "name": "my_logger", "process": {"id": 123, "name": "MainProcess"}, "thread": {"id": 456, "name": "MainThread"}, "time": {"repr": "2025-04-25 23:02:19.966+00:00", "timestamp": 1745622139.966}}}'


@pytest.fixture
def mock_prompts(monkeypatch):
    """Fixture to mock user inputs during the parse command using specific prompts."""

    def mock_ask(*args, **kwargs):
        prompt_message = args[0] # The first positional argument is the message
        if "Fields to include" in prompt_message:
            return "record.level.name, record.message, record.extra.app, record.extra.assay_id, record.extra.status.code"
        elif "Job name for these logs" in prompt_message:
            return "oxb_logs_test"
        elif "Dashboard name" in prompt_message:
            # Handle the case where dashboard name is prompted
            return "OXB Test Dashboard"
        elif "Label key" in prompt_message:
            # Return empty string to stop adding labels
            return ""
        elif "Value for" in prompt_message:
             # Should not be reached if Label key returns empty
             return "dummy_value"
        else:
            # Fallback for unexpected prompts
            print(f"WARN: Unexpected Prompt.ask call: {args} {kwargs}")
            return "unexpected_mock_input"

    # Expected order/values for Confirm.ask calls:
    # 1. Continue if no JSON? (True)
    # 2. Add custom labels? (False)
    confirm_inputs = iter([
        True,  # Continue if no JSON?
        False, # Add custom labels?
    ])

    # Patch Prompt.ask with our conditional function
    monkeypatch.setattr("rich.prompt.Prompt.ask", mock_ask)
    # Keep Confirm.ask simple for now
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: next(confirm_inputs))


def test_parse_command_loguru_json(tmp_path, mock_prompts):
    """Test the parse command with Loguru-style JSON logs and nested fields."""
    runner = CliRunner()
    base_dir = tmp_path / "lokikit_test_base"
    logs_dir = tmp_path / "test_logs"
    log_file_path = logs_dir / "app.log"

    # Create directories
    base_dir.mkdir()
    logs_dir.mkdir()

    # Create a dummy log file
    log_file_path.write_text(f"{SAMPLE_LOG_1}\n{SAMPLE_LOG_2}\n{SAMPLE_LOG_3}\n")

    # --- DEBUG: Verify sample log JSON validity ---
    try:
        json.loads(SAMPLE_LOG_1)
        json.loads(SAMPLE_LOG_2)
        json.loads(SAMPLE_LOG_3)
        print("DEBUG: Sample logs appear to be valid JSON.")
    except json.JSONDecodeError as e:
        print(f"DEBUG: Sample log JSON is invalid: {e}")
        # If this fails, the SAMPLE_LOG constants need fixing above.
        pytest.fail(f"Test setup failed: Sample log JSON is invalid - {e}")
    # --- END DEBUG ---

    # Create a basic initial promtail config (required by ensure_job_exists)
    initial_promtail_config_path = base_dir / "promtail-config.yaml"
    initial_promtail_config = {
        "server": {
            "http_listen_port": 9081, # Dummy port for test
            "grpc_listen_port": 0,
        },
        "positions": {"filename": str(base_dir / "positions.yaml")},
        "clients": [{"url": "http://localhost:3101/loki/api/v1/push"}], # Dummy URL
        "scrape_configs": [], # Start with no jobs
    }
    with open(initial_promtail_config_path, "w") as f:
        yaml.dump(initial_promtail_config, f)

    # --- Run the parse command ---
    result = runner.invoke(
        cli,
        [
            "--base-dir", str(base_dir),
            "parse", str(logs_dir),
            # "--dashboard-name", "My Test Dash", # Let the prompt handle it
            "--max-files", "1", # Limit for testing
            "--max-lines", "10", # Limit for testing
        ],
        catch_exceptions=False, # Let pytest handle exceptions for debugging
    )

    print(f"CLI Output:\n{result.output}")
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    # --- Verify Dashboard ---
    # Use the name provided in the mock prompt
    expected_dashboard_filename = "oxb_test_dashboard.json"
    dashboard_file = base_dir / "dashboards" / expected_dashboard_filename
    assert dashboard_file.exists(), f"Dashboard file '{expected_dashboard_filename}' was not created"

    with open(dashboard_file) as f:
        dashboard_data = json.load(f)

    assert dashboard_data["title"] == "OXB Test Dashboard"

    # Find the table panel (assuming ID 4 based on generator code)
    table_panel = next((p for p in dashboard_data.get("panels", []) if p.get("id") == 4), None)
    assert table_panel is not None, "Table panel (ID 4) not found in dashboard"
    assert table_panel["type"] == "table"

    # Check the table panel's query
    assert len(table_panel["targets"]) == 1, "Table panel should have one target"
    target = table_panel["targets"][0]
    # Basic check - more robust query check might be needed depending on build_loki_query specifics
    assert target["expr"] == '{job="oxb_logs_test"} | json'

    # Check field overrides for selected fields
    overrides = table_panel.get("fieldConfig", {}).get("overrides", [])
    selected_fields_expected = [
        "record.level.name",
        "record.message",
        "record.extra.app",
        "record.extra.assay_id", # This field exists in SAMPLE_LOG_1 extra
        "record.extra.status.code", # This nested field exists in SAMPLE_LOG_2 extra
    ]
    hidden_defaults = ["Line", "id", "tsNs", "labels", "job"]

    present_overrides = {o["matcher"]["options"]: o for o in overrides}

    for field in selected_fields_expected:
        assert field in present_overrides, f"Override for selected field '{field}' not found"
        # Check it's not hidden (unless it's 'level' or 'message' which have specific props)
        field_props = {prop["id"]: prop["value"] for prop in present_overrides[field]["properties"]}
        assert field_props.get("custom.hidden") is False, f"Selected field '{field}' is hidden"

    for field in hidden_defaults:
         if field in present_overrides: # Check if the override exists
             field_props = {prop["id"]: prop["value"] for prop in present_overrides[field]["properties"]}
             assert field_props.get("custom.hidden") is True, f"Default field '{field}' is not hidden"


    # --- Verify Promtail Config Update ---
    promtail_config_path = base_dir / "promtail-config.yaml"
    assert promtail_config_path.exists(), "Promtail config file not found after parse"

    with open(promtail_config_path) as f:
        promtail_config = yaml.safe_load(f)

    scrape_configs = promtail_config.get("scrape_configs", [])
    job_found = any(job.get("job_name") == "oxb_logs_test" for job in scrape_configs)
    assert job_found, "Job 'oxb_logs_test' not found in updated promtail config"

    # Check if the specific log path was added to the job
    job_config = next((job for job in scrape_configs if job.get("job_name") == "oxb_logs_test"), None)
    assert job_config is not None
    static_configs = job_config.get("static_configs", [])
    path_found = False
    expected_path_pattern = os.path.join(str(logs_dir), "**", "*.log") # Path added by watch_command
    for sc in static_configs:
        if sc.get("labels", {}).get("__path__") == expected_path_pattern:
            path_found = True
            break
    assert path_found, f"Expected log path pattern '{expected_path_pattern}' not found for job 'oxb_logs_test'"
