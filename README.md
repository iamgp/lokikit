# lokikit

A minimal CLI to set up and run a local Loki+Promtail+Grafana stack.

## Usage

Install with [uv tools](https://docs.astral.sh/uv/guides/tools/):

```sh
uv tools install git+https://github.com/iamgp/lokikit.git
lokikit setup
lokikit start
```

Access Grafana at http://localhost:3000 with default credentials `admin/admin`.

## Configuration

You can configure lokikit using command-line options or a YAML configuration file:

```sh
# Using command-line options
lokikit --host 0.0.0.0 --port 4000 --loki-port 3200 --promtail-port 9081 start

# Using a configuration file
lokikit --config lokikit.yaml start
```

### Custom Log Paths

You can monitor custom log paths with Promtail in two ways:

1. **Using the `watch` command** (recommended):

```sh
# Add a path to watch for logs
lokikit watch /path/to/logs/*.log

# Add with a custom job name
lokikit watch --job my_app_logs /path/to/app/logs/*.log

# Add with custom labels for better filtering
lokikit watch --job nginx_logs --label env=prod --label service=web /var/log/nginx/*.log
```

2. **Using a configuration file**:

```yaml
# lokikit.yaml
promtail:
  log_paths:
    - /var/log/syslog
    - path: /path/to/app/logs/*.log
      job: my_application
      labels:
        app: my-app
```

See `lokikit.example.yaml` for a complete configuration example.

## Commands

- `lokikit setup` - Download binaries and create configuration files
- `lokikit start` - Start Loki, Promtail, and Grafana
- `lokikit start --background` - Start services in the background
- `lokikit status` - Check if services are running
- `lokikit stop` - Stop running services
- `lokikit watch PATH` - Add a log path to monitor
- `lokikit clean` - Remove all downloaded files and configurations

## Development

### Setup Development Environment

1. Clone the repository:
   ```sh
   git clone https://github.com/iamgp/lokikit.git
   cd lokikit
   ```

2. Create and activate a virtual environment:
   ```sh
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install development dependencies:
   ```sh
   pip install -e ".[dev]"
   ```

4. Set up pre-commit hooks:
   ```sh
   pip install pre-commit
   pre-commit install
   ```

### Development Tools

- **Linting**: We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting
  ```sh
  ruff check .       # Run linting
  ruff format .      # Format code
  ```

- **Type checking**: We use [BasedPyright](https://github.com/ananis25/basedpyright) for type checking
  ```sh
  basedpyright       # Run type checking
  ```

- **Testing**: We use pytest for testing
  ```sh
  pytest             # Run tests
  pytest --cov=lokikit tests/  # Run tests with coverage
  ```

### CI/CD

The project uses GitHub Actions for:
- Running tests on multiple Python versions
- Linting and type checking
- Publishing to PyPI on release

## Disclaimer

This project is not affiliated with or endorsed by Grafana Labs. Loki is a trademark of Grafana Labs.
