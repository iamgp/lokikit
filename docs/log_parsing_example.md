# LokiKit Log Parsing and Dashboard Generation Example

This example demonstrates how to use LokiKit's log parsing feature to analyze log files and create Grafana dashboards.

## Setup

First, ensure LokiKit is set up properly:

```bash
lokikit setup
```

## Creating Sample Log Files

For demonstration purposes, let's create sample JSON log files:

```python
import json
import os
from pathlib import Path

# Create a directory for sample logs
sample_log_dir = Path("/tmp/sample_logs")
sample_log_dir.mkdir(exist_ok=True)

# Sample JSON logs for an API service
api_logs = [
    {"timestamp": "2023-10-15T10:00:00", "level": "INFO", "message": "Server started", "host": "api.example.com", "pod": "api-1"},
    {"timestamp": "2023-10-15T10:01:30", "level": "INFO", "message": "Request processed", "method": "GET", "path": "/users", "duration_ms": 42, "status": 200, "pod": "api-1"},
    {"timestamp": "2023-10-15T10:02:15", "level": "ERROR", "message": "Database connection failed", "error": "Connection refused", "pod": "api-1"},
    {"timestamp": "2023-10-15T10:03:00", "level": "WARN", "message": "High response time", "method": "POST", "path": "/orders", "duration_ms": 1250, "status": 201, "pod": "api-2"},
    {"timestamp": "2023-10-15T10:04:45", "level": "INFO", "message": "Cache hit", "cache_key": "user:1001", "pod": "api-2"},
    {"timestamp": "2023-10-15T10:05:30", "level": "INFO", "message": "Request processed", "method": "GET", "path": "/products", "duration_ms": 78, "status": 200, "pod": "api-1"},
]

# Write API logs to file
with open(sample_log_dir / "api.log", "w") as f:
    for log in api_logs:
        f.write(json.dumps(log) + "\n")
```

## Running the Parse Command

To analyze the log files and create a dashboard, run:

```bash
lokikit parse /tmp/sample_logs --dashboard-name "API Monitoring Dashboard"
```

## Interactive Workflow

The parse command runs an interactive workflow:

### 1. Log Discovery

```
Searching for log files in: /tmp/sample_logs
Found 2 log files
```

### 2. Content Analysis

```
Analyzing log contents...
Discovered JSON fields:
┏━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field Name    ┃ Types ┃ Sample Values                   ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ cache_key     │ str   │ user:1001                       │
│ duration_ms   │ int   │ 42                              │
│               │       │ 1250                            │
│ error         │ str   │ Connection refused              │
│ host          │ str   │ api.example.com                 │
│ level         │ str   │ INFO                            │
│               │       │ ERROR                           │
│ message       │ str   │ Server started                  │
│               │       │ Request processed               │
│ method        │ str   │ GET                             │
│               │       │ POST                            │
│ path          │ str   │ /users                          │
│               │       │ /orders                         │
│ pod           │ str   │ api-1                           │
│               │       │ api-2                           │
│ status        │ int   │ 200                             │
│               │       │ 201                             │
│ timestamp     │ str   │ 2023-10-15T10:00:00             │
│               │       │ 2023-10-15T10:01:30             │
└───────────────┴───────┴─────────────────────────────────┘
```

### 3. Field Selection

```
Select fields to include in the dashboard:
Enter field names separated by commas, or 'all' for all fields
Fields to include: timestamp,level,message,method,path,status,duration_ms,pod
```

### 4. Job Configuration

```
Job name for these logs (sample_logs): api_logs
```

### 5. Custom Labels

```
Add custom labels for filtering? [y/n] (n): y

Label key (or empty to finish): app
Value for 'app': api-service

Label key (or empty to finish): environment
Value for 'environment': production

Label key (or empty to finish):
```

### 6. Dashboard Creation

```
Generating dashboard...
Creating dashboard...
Updating Promtail configuration...
Updating Promtail config...

Dashboard created: /home/user/.lokikit/dashboards/api_monitoring_dashboard.json
Job name: api_logs

Dashboard will be available at: http://127.0.0.1:3000/dashboards

Note: You may need to restart Promtail to pick up the configuration changes:
  lokikit stop --force and lokikit start
```

## Understanding Custom Labels

Custom labels are key-value pairs attached to your logs, providing:

1. **Filtering**: Filter logs by specific criteria in Grafana
2. **Organization**: Organize logs from different sources
3. **Context**: Add relevant metadata to logs
4. **Segmentation**: Enable viewing logs from multiple sources in isolation

### Label Application

When you add custom labels like `app=api-service` and `environment=production`:

#### 1. Promtail Configuration Update:

```yaml
scrape_configs:
  - job_name: api_logs
    static_configs:
      - targets:
          - localhost
        labels:
          job: api_logs
          app: api-service
          environment: production
          __path__: /tmp/sample_logs/**/*.log
```

#### 2. Dashboard Queries:

```
{job="api_logs", app="api-service", environment="production"}
```

#### 3. Grafana UI Filtering:

You can use these labels to filter logs in the Grafana UI across multiple applications, environments, or other dimensions.

## Generated Dashboard

The generated dashboard includes multiple visualization panels:

1. **Log Browser**: Raw logs with search and filter capabilities
2. **Log Levels Over Time**: Count of different log levels
3. **HTTP Status Codes**: Distribution of status codes
4. **API Response Time**: Graph of response times
5. **Logs by Pod**: Table of logs grouped by pod

## Viewing the Dashboard

Start or restart LokiKit services to view the dashboard:

```bash
# If services are already running, stop them first
lokikit stop --force

# Start services
lokikit start --background
```

Access your dashboard at `http://127.0.0.1:3000/dashboards` with default credentials (admin/admin).
