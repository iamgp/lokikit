# Using Custom Labels in Loki for Filtering Logs

Labels are a powerful feature in Loki that allow you to organize, filter, and query your logs efficiently. When using lokikit's `parse` and `watch` commands, you can add custom labels to your log streams to make them more searchable and provide additional context.

## What Are Labels?

Labels in Loki are key-value pairs attached to log streams. They serve as metadata that helps you:

1. **Filter logs**: Quickly narrow down logs based on various criteria
2. **Organize logs**: Group related logs together
3. **Add context**: Provide additional information about the logs

Unlike the content of logs themselves, labels are indexed in Loki, making filtering by labels extremely fast and efficient.

## Common Use Cases for Custom Labels

- **Environment**: `env=production`, `env=staging`, `env=development`
- **Application components**: `component=api`, `component=database`, `component=frontend`
- **Severity levels**: `level=error`, `level=warning`, `level=info`
- **Version information**: `version=1.2.3`, `release=sprint-45`
- **Infrastructure**: `region=us-west`, `datacenter=aws-1`, `host=server-01`
- **Team ownership**: `team=backend`, `team=data-science`

## Adding Custom Labels with lokikit

### Using the `parse` Command

When running `lokikit parse`, you will be interactively prompted to add custom labels:

```bash
$ lokikit parse /path/to/logs --dashboard-name "My Application Logs"
# ...
# During the interactive process:
Add custom labels for filtering? [y/N]: y
Label key (or empty to finish): env
Value for 'env': production
Label key (or empty to finish): component
Value for 'component': api
Label key (or empty to finish):
```

### Using the `watch` Command

You can directly add labels when using the `watch` command:

```bash
$ lokikit watch /path/to/logs --job "api_logs" --label "env=production" --label "component=api"
```

## Best Practices for Labels

1. **Keep it simple**: Use a small, focused set of labels that are most valuable for filtering
2. **Consistent naming**: Use consistent naming conventions across your log sources
3. **Avoid high cardinality**: Avoid using labels that have many unique values (like user IDs or timestamps)
4. **Meaningful values**: Use descriptive values that will make sense to others reviewing logs
5. **Plan for querying**: Design labels with your common query patterns in mind

## Querying Logs Using Labels in Grafana

Once you've added labels to your logs, you can leverage them in Grafana queries:

### Basic Label Matching

```
{job="api_logs", env="production"}
```

### Multiple Labels

```
{job="api_logs", env="production", component="auth"}
```

### Regular Expression Matching

```
{job="api_logs", env=~"prod.*"}
```

### Negative Matching

```
{job="api_logs", env!="development"}
```

## Advanced Label Techniques

### Dynamic Labels from Log Content

You can use Loki's processing pipeline to extract values from logs into labels.

For example, if your log contains a JSON field `{"user_id": "123"}`, you can create a label with:

```
{job="api_logs"} | json | label_format user_id=extracted.user_id
```

### Label Filters in Dashboard Variables

In Grafana, you can create dashboard variables based on label values for interactive filtering:

1. Create a variable with a Loki data source
2. Use this query to populate values: `label_values(env)`
3. Use the variable in your queries: `{job="api_logs", env="$env"}`

## Conclusion

Thoughtful use of custom labels in your Loki setup can dramatically improve your ability to search, filter, and analyze logs. When used consistently across your applications, labels create a unified logging taxonomy that makes troubleshooting and analysis more efficient.
