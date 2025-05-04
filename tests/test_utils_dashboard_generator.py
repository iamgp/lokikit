"""Tests for the dashboard generator utility module."""

import json
import os
import tempfile

import pytest

from lokikit.utils.dashboard_generator import build_loki_query, create_dashboard, save_dashboard


def test_create_dashboard_basic():
    """Test creating a dashboard with minimal options."""
    dashboard = create_dashboard(
        dashboard_name="Test Dashboard",
        fields=[],
    )

    assert dashboard["title"] == "Test Dashboard"
    assert dashboard["tags"] == ["lokikit", "generated"]
    assert len(dashboard["panels"]) == 1  # Just the logs panel
    assert dashboard["panels"][0]["type"] == "logs"


def test_create_dashboard_with_fields():
    """Test creating a dashboard with fields for a table panel."""
    fields = ["timestamp", "level", "message"]
    dashboard = create_dashboard(
        dashboard_name="Log Analysis",
        fields=fields,
        job_name="test_job",
        labels={"env": "test"},
    )

    assert dashboard["title"] == "Log Analysis"
    assert len(dashboard["panels"]) == 2  # Logs panel and table panel

    # Check logs panel
    logs_panel = dashboard["panels"][0]
    assert logs_panel["type"] == "logs"
    assert logs_panel["title"] == "Log Browser"
    assert logs_panel["targets"][0]["expr"] == '{job="test_job", env="test"}'

    # Check table panel
    table_panel = dashboard["panels"][1]
    assert table_panel["type"] == "table"
    assert table_panel["title"] == "Structured Fields"
    assert (
        table_panel["targets"][0]["expr"]
        == '{job="test_job", env="test"} | json | line_format "{{ extracted.timestamp, extracted.level, extracted.message }}"'
    )


def test_build_loki_query_empty():
    """Test building a Loki query with no parameters."""
    query = build_loki_query()
    assert query == "{}"


def test_build_loki_query_job_only():
    """Test building a Loki query with just a job name."""
    query = build_loki_query(job_name="test_job")
    assert query == '{job="test_job"}'


def test_build_loki_query_with_labels():
    """Test building a Loki query with labels."""
    query = build_loki_query(
        job_name="test_job",
        labels={"env": "test", "component": "api"},
    )
    # The order of labels in the query string can vary, so we need to check each part
    assert '{job="test_job"' in query
    assert 'env="test"' in query
    assert 'component="api"' in query


def test_build_loki_query_with_fields():
    """Test building a Loki query with field extraction."""
    query = build_loki_query(
        job_name="test_job",
        fields=["timestamp", "level", "message"],
    )
    assert (
        query == '{job="test_job"} | json | line_format "{{ extracted.timestamp, extracted.level, extracted.message }}"'
    )


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_save_dashboard(temp_dir):
    """Test saving a dashboard to a file."""
    # Create a simple dashboard to save
    dashboard = create_dashboard(
        dashboard_name="Test Dashboard",
        fields=["level", "message"],
    )

    # Save the dashboard
    dashboard_path = save_dashboard(dashboard, temp_dir, "Test Dashboard")

    # Check the file was created
    assert os.path.exists(dashboard_path)
    assert os.path.basename(dashboard_path) == "test_dashboard.json"

    # Read the file and verify contents
    with open(dashboard_path) as f:
        saved_dashboard = json.load(f)

    assert saved_dashboard["title"] == "Test Dashboard"
    assert saved_dashboard["tags"] == ["lokikit", "generated"]
    assert len(saved_dashboard["panels"]) == 2  # Logs panel and table panel
