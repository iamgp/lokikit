"""Log analysis utilities for LokiKit.

This module provides functions for analyzing log files, detecting formats,
and extracting field metadata to help generate effective dashboards.
"""

import json
import re
from collections import defaultdict
from typing import Any

# Log format detection constants
LOGFMT_PATTERN = re.compile(r'(\w+)=("[^"]*"|\S+)')
COMMON_TIMESTAMP_PATTERNS = [
    # ISO8601
    re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})'),
    # Common log format
    re.compile(r'\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}'),
    # Simple date time
    re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(,\d+)?'),
]

def analyze_log_format(lines: list[str]) -> dict[str, Any]:
    """Analyze a sample of log lines to determine format characteristics.

    Args:
        lines: A list of log lines to analyze

    Returns:
        A dictionary with format statistics and metadata
    """
    result = {
        "formats": {
            "json": 0,
            "logfmt": 0,
            "pattern": 0,
            "unstructured": 0
        },
        "total_lines": len(lines),
        "detected_patterns": [],
        "dominant_format": None,
        "common_prefix": None,
        "timestamp_format": None
    }

    # Skip empty lines
    valid_lines = [line for line in lines if line.strip()]
    if not valid_lines:
        return result

    # Analyze each line
    for line in valid_lines:
        line = line.strip()

        # Check for JSON format
        try:
            json.loads(line)
            result["formats"]["json"] += 1
            continue
        except json.JSONDecodeError:
            pass

        # Check for logfmt format
        if LOGFMT_PATTERN.search(line):
            matches = LOGFMT_PATTERN.findall(line)
            if len(matches) >= 2:  # At least two key=value pairs
                result["formats"]["logfmt"] += 1
                continue

        # Check for common patterns
        has_timestamp = False
        for pattern in COMMON_TIMESTAMP_PATTERNS:
            if pattern.search(line):
                has_timestamp = True
                break

        if has_timestamp or re.search(r'(\[|\||\{)\s*(INFO|DEBUG|WARN|ERROR|TRACE)', line):
            result["formats"]["pattern"] += 1
            continue

        # Fallback to unstructured
        result["formats"]["unstructured"] += 1

    # Determine dominant format
    if valid_lines:
        format_counts = result["formats"]
        # Use itemgetter to fix max function
        from operator import itemgetter
        dominant_format = max(format_counts.items(), key=itemgetter(1))[0]
        dominant_percent = (format_counts[dominant_format] / len(valid_lines)) * 100

        result["dominant_format"] = dominant_format
        result["dominant_format_percent"] = dominant_percent

        # Detect common pattern if pattern-based
        if dominant_format == "pattern" and format_counts["pattern"] > 0:
            result["detected_patterns"] = detect_common_patterns(valid_lines)

    return result

def detect_common_patterns(lines: list[str]) -> list[dict]:
    """Detect common patterns in log lines.

    Args:
        lines: List of log lines to analyze

    Returns:
        List of detected patterns with regex and description
    """
    patterns = []

    # Check for common log patterns
    level_pattern = re.compile(r'(\[|\||\s)(INFO|DEBUG|WARN|ERROR|TRACE)(\]|\||:|\s)')
    timestamp_positions = []
    level_positions = []

    for line in lines[:20]:  # Sample a few lines
        # Find timestamps
        for pattern in COMMON_TIMESTAMP_PATTERNS:
            match = pattern.search(line)
            if match:
                timestamp_positions.append((match.start(), match.end()))
                break

        # Find log levels
        level_match = level_pattern.search(line)
        if level_match:
            level_positions.append((level_match.start(), level_match.end()))

    # If we have consistent positions, create patterns
    if timestamp_positions and all(p[0] == timestamp_positions[0][0] for p in timestamp_positions):
        pattern = {
            "description": "Timestamp at beginning",
            "regex": r'(?P<timestamp>\d{4}-\d{2}-\d{2}(T| )\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)',
            "sample_position": timestamp_positions[0]
        }
        patterns.append(pattern)

    if level_positions and len({p[0] for p in level_positions}) <= 3:
        pattern = {
            "description": "Log level",
            "regex": r'(?P<level>(INFO|DEBUG|WARN|ERROR|TRACE))',
            "sample_position": level_positions[0]
        }
        patterns.append(pattern)

    return patterns

def extract_json_fields(json_logs: list[dict]) -> dict[str, dict[str, Any]]:
    """Extract field information from a list of JSON logs.

    Args:
        json_logs: List of parsed JSON log objects

    Returns:
        Dictionary mapping field paths to metadata
    """
    fields = {}

    for log in json_logs:
        extract_fields_from_dict(log, "", fields)

    # Process extracted fields to add metadata
    for field_name, values in fields.items():
        field_metadata = analyze_field_values(values)
        fields[field_name] = field_metadata

    return fields

def extract_fields_from_dict(data: dict, prefix: str, fields: dict[str, list]) -> None:
    """Recursively extract fields from a dictionary.

    Args:
        data: The dictionary to process
        prefix: Current path prefix for nested fields
        fields: Dictionary to collect field values
    """
    for key, value in data.items():
        field_name = f"{prefix}{key}" if prefix else key

        # Initialize field if not seen before
        if field_name not in fields:
            fields[field_name] = []

        # Store the value unless it's a complex type
        if not isinstance(value, dict | list):
            fields[field_name].append(value)

        # Recursively process nested dictionaries
        if isinstance(value, dict):
            extract_fields_from_dict(value, f"{field_name}.", fields)

        # Handle lists that contain dictionaries
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Add array notation and process first item as example
            array_prefix = f"{field_name}[0]."
            extract_fields_from_dict(value[0], array_prefix, fields)

def analyze_field_values(values: list) -> dict[str, Any]:
    """Analyze a list of field values to determine type and metadata.

    Args:
        values: List of values for a field

    Returns:
        Dictionary with field metadata
    """
    # Skip empty lists
    if not values:
        return {
            "type": "unknown",
            "cardinality": 0,
            "cardinality_class": "unknown",
            "sample_values": []
        }

    # Count unique values
    unique_values = set()
    type_counts = defaultdict(int)
    numeric_values = []

    for value in values:
        # Track value type
        value_type = type(value).__name__
        type_counts[value_type] += 1

        # Add to unique values set (convert to string for consistency)
        unique_values.add(str(value))

        # Collect numeric values for additional analysis
        if isinstance(value, int | float):
            numeric_values.append(value)

    # Determine predominant type
    if type_counts:
        # Use itemgetter to fix max function
        from operator import itemgetter
        predominant_type = max(type_counts.items(), key=itemgetter(1))[0]
    else:
        predominant_type = "unknown"

    # Classify field based on values and name heuristics
    field_type = classify_field_type(predominant_type, values, unique_values)

    # Determine cardinality class
    cardinality = len(unique_values)
    total_values = len(values)
    cardinality_class = classify_cardinality(cardinality, total_values)

    # Get statistics for numeric fields
    numeric_stats = {}
    if numeric_values:
        numeric_stats = {
            "min": min(numeric_values),
            "max": max(numeric_values),
            "avg": sum(numeric_values) / len(numeric_values)
        }

    return {
        "type": field_type,
        "detected_type": predominant_type,
        "cardinality": cardinality,
        "cardinality_class": cardinality_class,
        "sample_values": list(unique_values)[:5],
        "numeric_stats": numeric_stats if numeric_values else None
    }

def classify_field_type(value_type: str, values: list, unique_values: set[str]) -> str:
    """Classify a field based on its values and patterns.

    Args:
        value_type: The predominant Python type of the values
        values: List of field values
        unique_values: Set of unique string representations

    Returns:
        Field classification (time, category, number, text)
    """
    # Check for timestamp fields
    if value_type == "str":
        # Sample a few values
        sample = [str(v) for v in values[:10] if v]

        # Check if they match timestamp patterns
        timestamp_matches = 0
        for value in sample:
            for pattern in COMMON_TIMESTAMP_PATTERNS:
                if pattern.fullmatch(value):
                    timestamp_matches += 1
                    break

        # If most samples look like timestamps
        if timestamp_matches >= len(sample) * 0.8:
            return "time"

    # Numeric fields
    if value_type in ("int", "float"):
        return "number"

    # Categorical fields - low to medium cardinality strings
    if value_type == "str" and len(unique_values) < 100:
        return "category"

    # Everything else is text
    return "text"

def classify_cardinality(cardinality: int, total_values: int) -> str:
    """Classify the cardinality of a field.

    Args:
        cardinality: Number of unique values
        total_values: Total number of values

    Returns:
        Cardinality classification (low, medium, high)
    """
    if cardinality <= 1:
        return "constant"
    elif cardinality <= 5:
        return "low"
    elif cardinality <= 50:
        return "medium"
    elif cardinality / total_values >= 0.9:
        return "unique"
    else:
        return "high"

def recommend_visualizations(fields: dict[str, dict]) -> list[dict[str, Any]]:
    """Recommend visualizations based on field metadata.

    Args:
        fields: Dictionary of fields with metadata

    Returns:
        List of visualization recommendations
    """
    recommendations = []

    for field_name, metadata in fields.items():
        # Skip format_detected and other special fields
        if field_name in ["format_detected"]:
            continue

        field_type = metadata["type"]
        cardinality_class = metadata["cardinality_class"]

        if field_type == "number":
            recommendations.append({
                "field": field_name,
                "panel_type": "time_series",
                "title": f"{field_name.replace('.', ' ')} Over Time",
                "description": "Time series visualization of numeric values"
            })

        elif field_type == "category" and cardinality_class in ("low", "medium"):
            recommendations.append({
                "field": field_name,
                "panel_type": "pie" if cardinality_class == "low" else "bar",
                "title": f"{field_name.replace('.', ' ')} Distribution",
                "description": f"Distribution of {metadata['cardinality']} distinct values"
            })

        elif field_type == "time":
            # Time fields are typically used for filtering, not visualized directly
            pass

        elif field_type == "text" and cardinality_class != "unique":
            recommendations.append({
                "field": field_name,
                "panel_type": "table",
                "title": f"{field_name.replace('.', ' ')} Values",
                "description": "Table of text values"
            })

    return recommendations

def generate_logql_query(job_name: str, log_format: str, field: str = "",
                          operation: str = "", interval: str = "5m") -> str:
    """Generate a LogQL query based on log format and field.

    Args:
        job_name: The Loki job name
        log_format: The format of the logs (json, logfmt, pattern)
        field: Optional field to extract/process
        operation: Optional operation (count, rate, unwrap)
        interval: Time interval for aggregations (default: 5m)

    Returns:
        LogQL query string
    """
    # Base query with job filter
    base_query = f'{{job="{job_name}"}}'

    # Field extraction based on format
    if log_format == "json":
        # For JSON logs
        query = f"{base_query} | json"

        # Handle nested fields
        if field and "." in field:
            parts = field.split(".")
            # Check for array notation
            if "[" in parts[0] and "]" in parts[0]:
                # Complex case with array access
                query = f'{base_query} | json field="{field}"'
            else:
                # Nested fields case
                leaf_name = parts[-1]
                query += f' | label_format {leaf_name}="{field}"'

    elif log_format == "logfmt":
        # For logfmt logs
        query = f"{base_query} | logfmt"

    elif log_format == "pattern":
        # For pattern-based logs
        # This would need a detected pattern from analyze_log_format
        query = f"{base_query} | pattern"

    else:
        # Default for unstructured logs
        query = base_query

    # Add operations
    if operation:
        if operation == "count" and field:
            query += f" | count_over_time([{interval}]) by ({field})"
        elif operation == "rate" and field:
            query += f" | unwrap {field} | rate([{interval}])"
        elif operation == "unwrap" and field:
            query += f" | unwrap {field}"

    return query
