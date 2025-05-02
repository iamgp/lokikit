"""Command implementations for lokikit CLI."""

import os
import shutil
import sys
import click
import yaml

from lokikit.config import (
    ensure_dir,
    write_config,
    LOKI_CONFIG_TEMPLATE,
    PROMTAIL_CONFIG_TEMPLATE,
    update_promtail_config,
)
from lokikit.download import (
    get_binaries,
    download_and_extract,
    find_grafana_binary,
    get_binary_path,
)
from lokikit.process import (
    start_process,
    write_pid_file,
    read_pid_file,
    check_services_running,
    wait_for_services,
    stop_services,
)

def setup_command(ctx):
    """Download binaries and write config files."""
    base_dir = ctx.obj["BASE_DIR"]
    host = ctx.obj["HOST"]
    grafana_port = ctx.obj["GRAFANA_PORT"]
    loki_port = ctx.obj["LOKI_PORT"]
    promtail_port = ctx.obj["PROMTAIL_PORT"]
    config = ctx.obj["CONFIG"]

    ensure_dir(base_dir)
    binaries = get_binaries(base_dir)
    print(f"Using Loki/Promtail version: {binaries['loki']['version']}")
    print(f"Using Grafana version: {binaries['grafana']['version']}")

    # Loki and Promtail
    for name in ["loki", "promtail"]:
        bin_path = os.path.join(base_dir, binaries[name]["binary"])
        if os.path.exists(bin_path):
            print(f"{name.capitalize()} binary already exists at {bin_path}, skipping download.")
        else:
            download_and_extract(binaries[name]["url"], base_dir, binaries[name]["filename"])
            if binaries["os_name"] != "windows":
                os.chmod(bin_path, 0o755)

    # Grafana
    grafana_bin = find_grafana_binary(
        base_dir,
        binaries["grafana"]["binary_name"],
        binaries["grafana"]["version"]
    )

    if grafana_bin and os.path.exists(grafana_bin):
        print(f"Grafana binary already exists at {grafana_bin}, skipping download.")
    else:
        download_and_extract(binaries["grafana"]["url"], base_dir, binaries["grafana"]["filename"])
        grafana_bin = find_grafana_binary(
            base_dir,
            binaries["grafana"]["binary_name"],
            binaries["grafana"]["version"]
        )

        if grafana_bin:
            if binaries["os_name"] != "windows":
                os.chmod(grafana_bin, 0o755)
        else:
            print("Warning: Could not find grafana-server binary after extraction.")

    # Generate configs with the specified host and ports
    loki_config = LOKI_CONFIG_TEMPLATE.format(
        host=host,
        loki_port=loki_port
    )

    # Get custom Promtail configuration if specified
    promtail_config = PROMTAIL_CONFIG_TEMPLATE.format(
        host=host,
        loki_port=loki_port,
        promtail_port=promtail_port
    )

    # Apply custom log paths if specified in config
    if "promtail" in config and "log_paths" in config["promtail"]:
        # Create a modified promtail config with custom log paths
        custom_targets = []
        for i, log_path in enumerate(config["promtail"]["log_paths"]):
            # Extract job name if provided, otherwise use an auto-generated name
            if isinstance(log_path, dict) and "path" in log_path and "job" in log_path:
                path = log_path["path"]
                job = log_path["job"]
                custom_labels = log_path.get("labels", {})
            else:
                # If it's just a string path
                path = log_path if isinstance(log_path, str) else log_path.get("path", "")
                job = f"logfile_{i}"
                custom_labels = {}

            if not path:
                continue

            # Format labels as YAML
            labels_yaml = "          job: " + job + "\n"
            for label_key, label_value in custom_labels.items():
                labels_yaml += f"          {label_key}: {label_value}\n"

            target = f"""
  - job_name: {job}
    static_configs:
      - targets:
          - localhost
        labels:
{labels_yaml}          __path__: {path}
"""
            custom_targets.append(target)

        # Replace the default scrape_config with our custom ones
        if custom_targets:
            base_config = """server:
  http_listen_port: {promtail_port}
  http_listen_address: {host}
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://{host}:{loki_port}/loki/api/v1/push

scrape_configs:""".format(
                host=host,
                loki_port=loki_port,
                promtail_port=promtail_port
            )

            promtail_config = base_config + "".join(custom_targets)
            print("Using custom log paths from configuration.")

    # Write config files
    write_config(os.path.join(base_dir, "loki-config.yaml"), loki_config)
    write_config(os.path.join(base_dir, "promtail-config.yaml"), promtail_config)

    # Create Grafana provisioning directories for datasource
    if grafana_bin:
        grafana_home = os.path.dirname(os.path.dirname(grafana_bin))
        grafana_provisioning_dir = os.path.join(grafana_home, "conf", "provisioning")
        grafana_datasources_dir = os.path.join(grafana_provisioning_dir, "datasources")
        ensure_dir(grafana_datasources_dir)

        # Create Loki datasource provisioning config
        loki_datasource_config = {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "Loki",
                    "type": "loki",
                    "access": "proxy",
                    "url": f"http://{host}:{loki_port}",
                    "isDefault": True,
                    "jsonData": {
                        "maxLines": 1000
                    }
                }
            ]
        }

        # Write datasource config
        loki_ds_config_path = os.path.join(grafana_datasources_dir, "loki.yaml")
        with open(loki_ds_config_path, "w") as f:
            yaml.dump(loki_datasource_config, f, default_flow_style=False)

        print(f"Created Loki datasource configuration for Grafana at {loki_ds_config_path}")

    print("Setup complete.")

def start_command(ctx, background, force, timeout):
    """Start Loki, Promtail, and Grafana."""
    base_dir = ctx.obj["BASE_DIR"]
    host = ctx.obj["HOST"]
    grafana_port = ctx.obj["GRAFANA_PORT"]
    loki_port = ctx.obj["LOKI_PORT"]
    promtail_port = ctx.obj["PROMTAIL_PORT"]

    # Check if services are already running
    existing_pids = read_pid_file(base_dir)
    if existing_pids and check_services_running(existing_pids) and not force:
        print(f"Services are already running with PIDs: {existing_pids}")
        print(f"- Grafana: http://{host}:{grafana_port}")
        print(f"  (Default credentials: admin/admin)")
        print(f"- Loki API: http://{host}:{loki_port}/loki/api/v1/labels")
        print(f"  (Loki has no UI - access through Grafana or use API endpoints)")
        print(f"- Promtail: http://{host}:{promtail_port}")
        print("Use --force to start anyway.")
        if not background:
            print("Press Ctrl+C to exit or run 'lokikit stop' from another terminal to stop the services.")
            try:
                import signal
                signal.pause()
            except KeyboardInterrupt:
                print("Exiting without stopping services. Run 'lokikit stop' to stop them.")
        return

    # Stop existing services if forcing
    if existing_pids and force:
        print("Stopping existing services first...")
        stop_services(existing_pids)
        # Delete pid file
        pid_file = os.path.join(base_dir, "lokikit.pid")
        if os.path.exists(pid_file):
            os.remove(pid_file)

    # Get binaries
    binaries = get_binaries(base_dir)
    loki_bin = get_binary_path("loki", binaries, base_dir)
    promtail_bin = get_binary_path("promtail", binaries, base_dir)
    grafana_bin = get_binary_path("grafana", binaries, base_dir)

    if not all([loki_bin, promtail_bin, grafana_bin]):
        missing = []
        if not loki_bin: missing.append("loki")
        if not promtail_bin: missing.append("promtail")
        if not grafana_bin: missing.append("grafana")
        print(f"Error: Missing binaries {', '.join(missing)}. Please run 'lokikit setup' first.")
        sys.exit(1)

    # Prepare log files and configs
    loki_cfg = os.path.join(base_dir, "loki-config.yaml")
    promtail_cfg = os.path.join(base_dir, "promtail-config.yaml")
    logs_dir = os.path.join(base_dir, "logs")
    ensure_dir(logs_dir)

    # Start processes
    procs = {}

    # Start Loki
    loki_log = os.path.join(logs_dir, "loki.log")
    procs["loki"] = start_process([loki_bin, "-config.file", loki_cfg], loki_log)

    # Start Promtail
    promtail_log = os.path.join(logs_dir, "promtail.log")
    procs["promtail"] = start_process([promtail_bin, "-config.file", promtail_cfg], promtail_log)

    # Start Grafana
    grafana_log = os.path.join(logs_dir, "grafana.log")
    grafana_home = os.path.dirname(os.path.dirname(grafana_bin))

    # Create Grafana provisioning directories and datasource config
    grafana_provisioning_dir = os.path.join(grafana_home, "conf", "provisioning")
    grafana_datasources_dir = os.path.join(grafana_provisioning_dir, "datasources")
    ensure_dir(grafana_datasources_dir)

    # Create Loki datasource provisioning config
    loki_datasource_config = {
        "apiVersion": 1,
        "datasources": [
            {
                "name": "Loki",
                "type": "loki",
                "access": "proxy",
                "url": f"http://{host}:{loki_port}",
                "isDefault": True,
                "jsonData": {
                    "maxLines": 1000
                }
            }
        ]
    }

    # Write datasource config
    loki_ds_config_path = os.path.join(grafana_datasources_dir, "loki.yaml")
    with open(loki_ds_config_path, "w") as f:
        yaml.dump(loki_datasource_config, f, default_flow_style=False)

    print(f"Created Loki datasource configuration for Grafana at {loki_ds_config_path}")

    # Use the classic grafana-server format
    grafana_cmd = [
        grafana_bin,
        "--homepath", grafana_home,
        "--config", os.path.join(grafana_home, "conf/defaults.ini"),
        "--configOverrides", f"server.http_addr={host};server.http_port={grafana_port}"
    ]

    procs["grafana"] = start_process(grafana_cmd, grafana_log)

    # Wait for services to start
    ports = {
        "loki": loki_port,
        "promtail": promtail_port,
        "grafana": grafana_port
    }
    success = wait_for_services(host, ports, procs, timeout)

    # Store process IDs for background mode and potential future operations
    pids = {name: proc.pid for name, proc in procs.items()}
    pid_file = write_pid_file(pids, base_dir)

    print(f"\nAll services started:")
    print(f"- Grafana: http://{host}:{grafana_port}")
    print(f"  (Default credentials: admin/admin)")
    print(f"- Loki API: http://{host}:{loki_port}/loki/api/v1/labels")
    print(f"  (Loki has no UI - access through Grafana or use API endpoints)")
    print(f"- Promtail: http://{host}:{promtail_port}")
    print(f"Log files are located in: {logs_dir}")

    if background:
        print(f"Running in background mode. PIDs stored in {pid_file}")
        print(f"To check status: lokikit status")
        print(f"To stop the services: lokikit stop")
        return
    else:
        print("\nPress Ctrl+C to stop the services.")
        try:
            # In foreground mode, wait for all processes
            # This keeps the process running in the foreground
            while all(proc.poll() is None for proc in procs.values()):
                import time
                time.sleep(1)

            # If we get here, at least one process has terminated
            print("One or more services have terminated unexpectedly.")
            for name, proc in procs.items():
                if proc.poll() is not None:
                    print(f"- {name} exited with code {proc.poll()}")
            print(f"Check the log files in {logs_dir} for details.")

        except KeyboardInterrupt:
            print("\nStopping services...")
            for name, proc in procs.items():
                try:
                    proc.terminate()
                    print(f"Terminated {name}")
                except:
                    pass

def stop_command(ctx, force):
    """Stop running services."""
    base_dir = ctx.obj["BASE_DIR"]
    pids = read_pid_file(base_dir)

    if not pids:
        print("No running services found.")
        return

    if force:
        import signal
        print("Force stopping services with SIGKILL...")
        for name, pid in pids.items():
            try:
                print(f"Killing {name} (PID: {pid})...")
                os.kill(pid, signal.SIGKILL)
            except OSError as e:
                if e.errno == 3:  # No such process
                    print(f"  Service {name} (PID: {pid}) was not running")
                else:
                    print(f"  Error killing {name}: {e}")
    else:
        stop_services(pids)

    # Remove PID file
    pid_file = os.path.join(base_dir, "lokikit.pid")
    if os.path.exists(pid_file):
        os.remove(pid_file)
        print("Removed PID file.")

    print("Operation completed.")

def status_command(ctx):
    """Check if services are running."""
    base_dir = ctx.obj["BASE_DIR"]
    host = ctx.obj["HOST"]
    grafana_port = ctx.obj["GRAFANA_PORT"]
    loki_port = ctx.obj["LOKI_PORT"]
    promtail_port = ctx.obj["PROMTAIL_PORT"]

    pids = read_pid_file(base_dir)

    if not pids:
        print("No services appear to be running.")
        return

    running = check_services_running(pids)

    if running:
        print("Services are running:")
        for name, pid in pids.items():
            print(f"- {name.capitalize()}: PID {pid}")
        print(f"\nAccess URLs:")
        print(f"- Grafana: http://{host}:{grafana_port}")
        print(f"  (Default credentials: admin/admin)")
        print(f"- Loki API: http://{host}:{loki_port}/loki/api/v1/labels")
        print(f"  (Loki has no UI - access through Grafana or use API endpoints)")
        print(f"- Promtail: http://{host}:{promtail_port}")
    else:
        print("Services are not running or have crashed.")
        print("Check the log files or run 'lokikit start' to restart them.")

def clean_command(ctx):
    """Remove all downloaded files and configs."""
    base_dir = ctx.obj["BASE_DIR"]

    # Check if services are running and stop them first
    pids = read_pid_file(base_dir)
    if pids and check_services_running(pids):
        print("Stopping running services first...")
        stop_services(pids)

    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        print("Cleaned up all files.")

def watch_command(ctx, path, job, label):
    """Add a log path to Promtail configuration."""
    base_dir = ctx.obj["BASE_DIR"]

    # Parse labels
    labels = {}
    for lbl in label:
        try:
            key, value = lbl.split("=", 1)
            labels[key.strip()] = value.strip()
        except ValueError:
            print(f"Warning: Ignoring invalid label format: {lbl}. Use key=value format.")

    # Update promtail config
    if update_promtail_config(base_dir, path, job, labels):
        # Check if services are running
        pids = read_pid_file(base_dir)
        if pids and check_services_running(pids):
            print("\nServices are currently running.")
            print("To apply changes, restart services with: lokikit stop && lokikit start")
    else:
        print("No changes made to Promtail configuration.")
