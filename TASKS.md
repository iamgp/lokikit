# Log Parsing and Grafana Dashboard Creation Feature

This feature enables users to parse logs in a watched folder and interactively create Grafana dashboards.

## Completed Tasks

- [x] Create task list file to track implementation progress
- [x] Add a new `parse` command to the CLI
- [x] Implement log file discovery in watched directories
- [x] Add interactive log field selection using Rich
- [x] Create Grafana dashboard from selected fields
- [x] Write dashboard JSON to appropriate location
- [x] Test the new parse command with various log formats
- [x] Add proper type annotations and fix linter errors
- [x] Write comprehensive tests for the new functionality

## Future Tasks

- [ ] Add support for custom dashboard templates
- [ ] Implement dashboard versioning
- [ ] Add ability to modify existing dashboards

## Implementation Plan

The feature allows users to parse logs from a specified directory, interactively select fields from log entries (especially JSON logs), and create a Grafana dashboard with relevant visualizations.

1. Added a new `parse` command to the CLI with options for dashboard name and sampling limits
2. The command scans the specified directory for log files (JSON, txt, log)
3. Using Rich, it provides an interactive interface to:
   - Display log samples and discovered fields
   - Allow selection of fields to include in the dashboard
   - Set job name and custom labels for filtering
4. Generates a Grafana dashboard JSON definition with logs and table panels
5. Saves the dashboard to the correct location and updates promtail configuration

### Relevant Files

- lokikit/cli.py - Added new parse command
- lokikit/commands.py - Implemented log parsing and dashboard creation logic
- lokikit/utils/dashboard_generator.py - Created utility to generate dashboard JSON
- lokikit/utils/__init__.py - Exported dashboard generator functions
- tests/test_utils_dashboard_generator.py - Added tests for dashboard generation utility
- tests/test_parse_command.py - Added tests for parse command
- tests/test_cli.py - Updated with tests for CLI integration
