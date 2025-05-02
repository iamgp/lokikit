# Logging Best Practices for LokiKit

This guide outlines best practices for structuring logs in your applications to work effectively with LokiKit and Grafana.

## Key Principles

1. **Use structured JSON logging** - Makes logs queryable and filterable in Grafana
2. **Include consistent metadata** - Add contextual information to every log entry
3. **Use proper log levels** - Apply appropriate severity levels to messages
4. **Add contextual information** - Include relevant business context with log entries
5. **Enable flexible filtering** - Design logs to support effective querying

## Recommended Structure

For optimal visualization and querying in Grafana via LokiKit, structure your logs as JSON with these key fields:

```json
{
  "timestamp": "2023-06-15T12:34:56.789Z",    // ISO-8601 timestamp
  "level": "INFO",                            // Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  "logger": "my_module.component",            // Logger name for component-level filtering
  "service": "my-application",                // Service/application name
  "message": "User login successful",         // Human-readable message
  "context": {                                // Business context (flexible structure)
    "user_id": "12345",
    "request_id": "req-abc-123",
    "tenant": "acme-corp"
  },
  "location": {                               // Source code location (optional)
    "file": "/app/auth.py",
    "line": 42,
    "function": "authenticate_user"
  }
}
```

Additional fields can be added as needed for your specific application.

## LokiKit's Approach

LokiKit uses Loguru with a balanced approach to logging:

1. **Loguru for simplicity** - Uses the intuitive and powerful Loguru library
2. **Structured JSON for log files** - All logs written to files are in structured JSON format
3. **Minimal console output** - Console logs show only the essential message text
4. **Contextual metadata** - Internal logs include version, location, and context information

This approach ensures:
- Logs are user-friendly in the terminal
- Log files are fully queryable with LogQL
- Detailed debugging information is available when needed

### Using Loguru in your applications

LokiKit enhances Loguru to provide multiple ways to add context to your logs:

```python
# 1. Direct kwargs approach (simplest)
logger.info("User logged in", user_id="12345", ip_address="192.168.1.1")

# 2. Explicit context parameter
logger.info("User logged in", context={"user_id": "12345", "ip_address": "192.168.1.1"})

# 3. Bind context to create a contextualized logger
user_logger = logger.bind(context={"user_id": "12345"})
user_logger.info("Profile updated")  # context is automatically included
user_logger.info("Settings changed", changes=["email", "password"])  # add more context

# 4. Temporary context with contextualize
with logger.contextualize(context={"request_id": "req-123"}):
    logger.info("Processing request")
    logger.info("Validation complete", status="success")  # with additional context
```

All of these approaches automatically structure the context data for optimal querying in Loki.

See the [logging example](logging_example.py) for a demonstration of how to use LokiKit's Loguru-based logging in your own applications.

## Sample Implementation

We provide a reference implementation in [recommended_logging.py](recommended_logging.py) that you can use as a starting point. It includes:

- JSON structured logging
- Context support through Loguru
- Configuration for file and console logging
- Example usage patterns

## Effective LogQL Queries

Once your logs are in Loki via LokiKit, you can use these LogQL query patterns in Grafana:

### Basic Filtering

```
{job="my-application"} | json | level="ERROR"
```

### Context-Based Filtering

```
{job="my-application"} | json | context.user_id="12345"
```

### Pattern Matching

```
{job="my-application"} | json | message=~".*failed.*"
```

### Combined Filters

```
{job="my-application"} | json | level="ERROR" and context.tenant="acme-corp"
```

### Extracting Fields for Visualization

```
{job="my-application"} | json | level="ERROR" | line_format "{{.timestamp}} - {{.message}}"
```

## Common Use Cases

### Error Analysis

```
{job="my-application"} | json | level="ERROR"
| line_format "{{.timestamp}} {{.message}} ({{.context.request_id}})"
```

### User Activity Tracking

```
{job="my-application"} | json | context.user_id="12345"
| line_format "{{.timestamp}} {{.level}} {{.message}}"
```

### Performance Monitoring

If you include timing information in your logs:

```
{job="my-application"} | json | context.operation="database_query"
| unwrap context.duration_ms | rate[5m]
```

## Integration with LokiKit

When using the `lokikit watch` command to monitor your application logs, ensure your log files have a consistent location and format. For example:

```sh
lokikit watch --job my_application --label service=my-app /path/to/logs/*.log
```

Then configure Grafana dashboards to visualize and analyze these logs using the recommended LogQL queries above.

## Recommendations for Log Volume

- Use appropriate log levels to control volume
- Consider sampling high-volume debug logs
- For high-throughput services, use batching or asynchronous logging
- Apply retention policies appropriate to your needs

## Testing Your Logging

Before deploying, test that your logs are correctly parsed in Loki by:

1. Running your application locally with LokiKit
2. Generating sample logs across different levels
3. Querying them in Grafana to ensure they're structured as expected
4. Verifying that all context fields are properly parseable
