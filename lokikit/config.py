"""Configuration module for lokikit."""

import os
import yaml

# Default configuration values
DEFAULT_BASE_DIR = os.path.expanduser("~/.lokikit")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_GRAFANA_PORT = 3000
DEFAULT_LOKI_PORT = 3100
DEFAULT_PROMTAIL_PORT = 9080

# Template configs with placeholders for host and port
LOKI_CONFIG_TEMPLATE = """auth_enabled: false
server:
  http_listen_port: {loki_port}
  http_listen_address: {host}
common:
  path_prefix: /tmp/loki
  storage:
    filesystem:
      chunks_directory: /tmp/loki/chunks
      rules_directory: /tmp/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100
schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h
limits_config:
  allow_structured_metadata: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
ruler:
  alertmanager_url: http://localhost:9093
"""

PROMTAIL_CONFIG_TEMPLATE = """server:
  http_listen_port: {promtail_port}
  http_listen_address: {host}
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://{host}:{loki_port}/loki/api/v1/push

scrape_configs:
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: varlogs
          __path__: /var/log/*.log
"""

def load_config_file(config_file):
    """Load configuration from YAML file."""
    if not os.path.exists(config_file):
        print(f"Warning: Config file {config_file} not found, using defaults.")
        return {}

    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except Exception as e:
        print(f"Error loading config file: {e}")
        return {}

def merge_config(cli_options, file_config):
    """Merge CLI options with file configuration, prioritizing CLI options."""
    result = {}

    # Start with file config
    if file_config:
        result.update(file_config)

    # Override with CLI options (only non-None values)
    for key, value in cli_options.items():
        if value is not None:
            result[key] = value

    return result

def write_config(filename, content):
    """Write content to a configuration file."""
    with open(filename, "w") as f:
        f.write(content)

def ensure_dir(path):
    """Ensure a directory exists."""
    if not os.path.exists(path):
        os.makedirs(path)

def update_promtail_config(base_dir, log_path, job_name=None, labels=None):
    """Update promtail config to add a new log path."""
    # Default values
    job_name = job_name or f"job_{hash(log_path) % 10000}"
    labels = labels or {}

    config_path = os.path.join(base_dir, "promtail-config.yaml")

    if not os.path.exists(config_path):
        print(f"Error: Promtail config not found at {config_path}. Run 'lokikit setup' first.")
        return False

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading Promtail config: {e}")
        return False

    # Ensure structure exists
    if not config:
        print("Error: Invalid Promtail config.")
        return False

    if "scrape_configs" not in config:
        config["scrape_configs"] = []

    # Convert log_path to absolute path if it's relative
    abs_log_path = os.path.expanduser(log_path)

    # Check if path already exists in config
    path_exists = False
    for job in config["scrape_configs"]:
        for static_config in job.get("static_configs", []):
            for target_labels in static_config.get("labels", {}).items():
                if "__path__" in target_labels and target_labels["__path__"] == abs_log_path:
                    path_exists = True
                    print(f"Path {abs_log_path} is already being watched.")
                    break

    if not path_exists:
        # Create new job config
        new_job = {
            "job_name": job_name,
            "static_configs": [
                {
                    "targets": ["localhost"],
                    "labels": {
                        "job": job_name,
                        "__path__": abs_log_path
                    }
                }
            ]
        }

        # Add custom labels
        for key, value in labels.items():
            new_job["static_configs"][0]["labels"][key] = value

        config["scrape_configs"].append(new_job)

        # Write updated config
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"Added {abs_log_path} to Promtail configuration with job name '{job_name}'.")
        return True

    return False
