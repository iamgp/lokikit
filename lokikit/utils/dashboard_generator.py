"""Utilities for generating Grafana dashboards from log data."""

import json
import os
import uuid


def create_dashboard(
    dashboard_name: str,
    fields: list[str],
    job_name: str | None = None,
    labels: dict[str, str] | None = None,
) -> dict:
    """Create a Grafana dashboard JSON for the given fields.

    Args:
        dashboard_name: Name for the dashboard
        fields: List of log fields to include in the dashboard
        job_name: Optional job name for filtering logs
        labels: Optional additional labels for filtering logs

    Returns:
        Dictionary containing the dashboard JSON definition
    """
    if not dashboard_name:
        dashboard_name = "Log Analysis Dashboard"

    # Generate a unique ID for the dashboard
    uid = str(uuid.uuid4())[:8]

    # Base dashboard structure
    dashboard = {
        "uid": uid,
        "title": dashboard_name,
        "tags": ["lokikit", "generated"],
        "timezone": "browser",
        "editable": True,
        "liveNow": True,
        "style": "dark",
        "graphTooltip": 0,
        "time": {"from": "now-1h", "to": "now"},
        "panels": [],
        "refresh": "10s",
        "schemaVersion": 38,
        "version": 1,
    }

    # Create a logs panel
    logs_panel = {
        "id": 1,
        "title": "Log Browser",
        "type": "logs",
        "datasource": {"type": "loki", "uid": "lokikit"},
        "gridPos": {"h": 10, "w": 24, "x": 0, "y": 0},
        "targets": [{"refId": "A", "expr": build_loki_query(job_name, labels), "queryType": "range"}],
        "options": {
            "showLabels": False,
            "showTime": True,
            "sortOrder": "Descending",
            "wrapLogMessage": True,
            "dedupStrategy": "none",
            "enableLogDetails": True,
            "prettifyLogMessage": True,
        },
    }

    dashboard["panels"].append(logs_panel)

    # Create a table panel for structured fields
    if fields:
        table_panel = {
            "id": 2,
            "title": "Structured Fields",
            "type": "table",
            "datasource": {"type": "loki", "uid": "lokikit"},
            "gridPos": {"h": 12, "w": 24, "x": 0, "y": 10},
            "targets": [
                {
                    "refId": "A",
                    "expr": build_loki_query(job_name, labels, fields),
                    "queryType": "instant",
                    "legendFormat": "",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "filterable": True},
                    "mappings": [],
                    "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
                },
                "overrides": [],
            },
            "options": {
                "footer": {"enablePagination": True, "fields": "", "reducer": ["sum"], "show": False},
                "showHeader": True,
            },
        }

        dashboard["panels"].append(table_panel)

    return dashboard


def build_loki_query(
    job_name: str | None = None,
    labels: dict[str, str] | None = None,
    fields: list[str] | None = None,
) -> str:
    """Build a Loki query string with the given parameters.

    Args:
        job_name: Optional job name for filtering logs
        labels: Optional additional labels for filtering logs
        fields: Optional list of fields to extract

    Returns:
        Loki query string
    """
    # Start with base selector
    query = "{"

    # Add job selector if provided
    if job_name:
        query += f'job="{job_name}"'

    # Add additional labels
    if labels:
        for key, value in labels.items():
            # Add comma if needed
            if query[-1] != "{":
                query += ", "
            query += f'{key}="{value}"'

    # Close selector
    if query[-1] == "{":
        # No labels were added, match everything
        query += ""

    query += "}"

    # Add field extraction if requested
    if fields:
        fields_expr = ", ".join([f"extracted.{field}" for field in fields])
        query += f' | json | line_format "{{{{ {fields_expr} }}}}"'

    return query


def save_dashboard(dashboard: dict, base_dir: str, dashboard_name: str) -> str:
    """Save the dashboard JSON to the appropriate location.

    Args:
        dashboard: Dashboard JSON dictionary
        base_dir: Base directory for lokikit
        dashboard_name: Name for the dashboard file

    Returns:
        Path to the saved dashboard file
    """
    # Ensure dashboards directory exists
    dashboards_dir = os.path.join(base_dir, "dashboards")
    os.makedirs(dashboards_dir, exist_ok=True)

    # Clean dashboard name for filename
    clean_name = dashboard_name.lower().replace(" ", "_")
    if not clean_name.endswith(".json"):
        clean_name += ".json"

    # Save dashboard JSON
    dashboard_path = os.path.join(dashboards_dir, clean_name)
    with open(dashboard_path, "w") as f:
        json.dump(dashboard, f, indent=2)

    return dashboard_path
