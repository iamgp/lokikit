# Log Parsing and Dashboard Generation

This guide explains how to use LokiKit's log parsing and dashboard generation feature to analyze your log files and create custom Grafana dashboards.

## Overview

The `parse` command allows you to:

1. Scan directories for log files
2. Analyze log structure and content
3. Detect fields in JSON-formatted logs
4. Interactively select fields to monitor
5. Create a Grafana dashboard with visualizations
6. Configure Promtail to collect and forward logs

This feature is particularly powerful for JSON-structured logs, as it can automatically extract and visualize fields within the logs.

## Command Syntax

```
lokikit parse [OPTIONS] DIRECTORY
```

### Arguments

- `DIRECTORY`: Path to the directory containing log files to analyze (required)

### Options

- `--dashboard-name TEXT`: Name for the generated Grafana dashboard
- `--max-files INTEGER`: Maximum number of log files to sample (default: 5)
- `--max-lines INTEGER`: Maximum number of lines to sample per file (default: 100)
- `--help`: Show help message and exit

## Workflow

When you run the `parse` command, it follows this interactive workflow:

1. **Log Discovery**: Scans the specified directory for log files (`.log`, `.json`, `.txt`)
2. **Content Analysis**: Analyzes log files to detect JSON structure and fields
3. **Field Selection**: Displays discovered fields and lets you select which ones to include in the dashboard
4. **Job Configuration**:
   - Sets a job name for Promtail configuration
   - Allows adding custom labels for filtering
5. **Dashboard Generation**: Creates a Grafana dashboard with appropriate visualizations
6. **Configuration Update**: Updates Promtail configuration to collect the logs

## Custom Labels for Filtering

### What Are Custom Labels?

Custom labels are key-value pairs attached to your log entries in Loki. They serve several important purposes:

1. **Filtering**: Allow you to filter logs in Grafana based on specific criteria
2. **Organization**: Help organize logs from different sources or applications
3. **Context**: Add relevant metadata to your logs
4. **Segmentation**: Enable viewing logs from multiple sources in isolation

### How Labels Work in Loki

In Loki, labels are the primary way to query and filter logs. The labels are indexed, while the log content itself is not indexed until you run a query. This is what makes Loki efficient compared to other log systems.

When you add a custom label during log parsing, it gets:

1. Added to the Promtail configuration for the specific log path
2. Included in all Loki queries in the generated dashboard
3. Made available as a filter in the Grafana UI

### Example Label Use Cases

| Label Key      | Example Values           | Purpose                                     |
|----------------|--------------------------|---------------------------------------------|
| `app`          | `api`, `frontend`, `db`  | Identify which application generated the log|
| `environment`  | `prod`, `staging`, `dev` | Distinguish between deployment environments |
| `component`    | `auth`, `payment`, `user`| Specify a component within an application   |
| `region`       | `us-east`, `eu-west`     | Geographical location of the service        |
| `customer`     | `customer1`, `customer2` | For multi-tenant applications              |
| `version`      | `v1.0`, `v1.1`           | Track logs across software versions         |

### Best Practices for Labels

1. **Keep labels consistent** across all your log sources
2. **Use a small number** of label key-value pairs (ideally under 10)
3. **Avoid high-cardinality labels** (labels with many possible values)
4. **Choose labels for categorization**, not for detailed log content
5. **Use hierarchical naming** for related labels (e.g., `kubernetes_namespace`, `kubernetes_pod_name`)

## Dashboard Generation

### Types of Panels Generated

Based on the fields you select, the dashboard generator creates several types of panels:

1. **Logs Panel**: Raw logs with search and filter capabilities
2. **Table Panel**: Structured view of selected fields from your logs
3. **Time Series Panel**: For numeric fields that can be plotted over time
4. **Stat Panels**: For metrics like error counts or response times
5. **Pie Charts**: For categorical data, such as status codes or log levels

### Dashboard Layout

The dashboard is organized with:

- A logs panel at the top for overall log viewing
- Field-specific visualizations below, arranged in a grid
- Appropriate time ranges and refresh intervals
- Consistent styling and labeling

### Example Dashboard

A typical dashboard for API logs might include:

- **Log Browser**: Raw logs with filtering
- **Log Levels Chart**: Counts of INFO, WARN, ERROR logs over time
- **Response Times**: Graph of API response times
- **Status Codes**: Distribution of HTTP status codes
- **Errors Table**: Detailed view of error messages
- **Endpoint Traffic**: Requests per API endpoint

## Examples

### Basic Usage

Analyze all logs in a directory:

```bash
lokikit parse /var/log/myapp
```

### Custom Dashboard Name

Specify a custom name for the dashboard:

```bash
lokikit parse /var/log/myapp --dashboard-name "MyApp Dashboard"
```

### Limiting Sample Size

For large log directories:

```bash
lokikit parse /var/log/myapp --max-files 10 --max-lines 200
```

### Multiple Log Types

Process different log types with separate commands:

```bash
# API logs
lokikit parse /var/log/api --dashboard-name "API Dashboard"

# Database logs
lokikit parse /var/log/db --dashboard-name "Database Dashboard"
```

## Field Selection Tips

When selecting fields to include in your dashboard, consider:

1. **Timestamp fields**: Essential for time-based visualization
2. **Log levels**: Useful for tracking error rates
3. **Status codes/results**: Help monitor success/failure rates
4. **Duration/timing fields**: Good for performance monitoring
5. **User/customer IDs**: Helpful for investigating user-specific issues
6. **Resource utilization**: Memory, CPU, connections, etc.

## Interactive Workflow Example

Here's an example of what to expect when running the command:

```
$ lokikit parse /var/log/api --dashboard-name "API Dashboard"

Searching for log files in: /var/log/api
Found 3 log files

Analyzing log contents...
Discovered JSON fields:
┏━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field Name    ┃ Types ┃ Sample Values                   ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ duration_ms   │ int   │ 42                              │
│ level         │ str   │ INFO                            │
│ message       │ str   │ Server started                  │
│ method        │ str   │ GET                             │
│ path          │ str   │ /users                          │
│ status        │ int   │ 200                             │
│ timestamp     │ str   │ 2023-10-15T10:00:00             │
└───────────────┴───────┴─────────────────────────────────┘

Select fields to include in the dashboard:
Enter field names separated by commas, or 'all' for all fields
Fields to include: timestamp,level,message,method,path,status,duration_ms

Job name for these logs (api): api_logs

Add custom labels for filtering? [y/n] (n): y

Label key (or empty to finish): app
Value for 'app': api-service

Label key (or empty to finish): environment
Value for 'environment': production

Label key (or empty to finish):

Generating dashboard...
Dashboard created: /home/user/.lokikit/dashboards/api_dashboard.json
Job name: api_logs

Dashboard will be available at: http://127.0.0.1:3000/dashboards

Note: You may need to restart Promtail to pick up the configuration changes:
  lokikit stop --force and lokikit start
```

## Troubleshooting

### No JSON Fields Detected

If no JSON fields are detected:
- Verify your logs are in JSON format
- Check if the logs have line breaks that might break JSON parsing
- Try increasing `--max-lines` to sample more of each file

### Dashboard Not Showing in Grafana

If your dashboard doesn't appear in Grafana:
- Make sure Grafana is running (`lokikit status`)
- Restart LokiKit services (`lokikit stop --force && lokikit start`)
- Check if Loki datasource is properly configured
- Verify the dashboard was created at the expected location

### No Data in Dashboard

If your dashboard shows no data:
- Ensure Promtail is running and monitoring the correct paths
- Check if logs are being ingested into Loki
- Verify the job name and labels in the Loki query match what's in Promtail config
- Try using the Loki Explore interface in Grafana to troubleshoot queries

## Customizing Generated Dashboards

After generation, you can further customize your dashboard:
1. Open the dashboard in Grafana
2. Click the settings (gear) icon
3. Edit panels, add new panels, or adjust layouts
4. Save your customized version

The dashboard JSON file is also saved to disk at:
```
~/.lokikit/dashboards/{dashboard_name}.json
```

You can edit this file directly if desired.

## Conclusion

The log parsing and dashboard generation feature provides a quick way to gain insights from your log files. By intelligently detecting log structure and offering appropriate visualizations, it reduces the manual effort of setting up log monitoring.

As your logging needs evolve, you can run the parse command for different log sources, create specialized dashboards, and build a comprehensive logging ecosystem with minimal configuration.
