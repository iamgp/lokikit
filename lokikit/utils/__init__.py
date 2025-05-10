"""
LokiKit utility modules.
"""

from lokikit.utils.dashboard_generator import create_dashboard, save_dashboard
from lokikit.utils.job_manager import ensure_job_exists, get_job_names
from lokikit.utils.log_analyzer import (
    analyze_log_format,
    extract_json_fields,
    recommend_visualizations,
    generate_logql_query
)

__all__ = [
    "create_dashboard",
    "save_dashboard",
    "ensure_job_exists",
    "get_job_names",
    "analyze_log_format",
    "extract_json_fields",
    "recommend_visualizations",
    "generate_logql_query"
]
