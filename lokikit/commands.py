"""Command implementations for lokikit CLI."""

import os
import shutil
import signal
import subprocess
import sys
import time

import yaml

from lokikit.config import (
    LOKI_CONFIG_TEMPLATE,
    PROMTAIL_CONFIG_TEMPLATE,
    ensure_dir,
    update_promtail_config,
    write_config,
)
from lokikit.download import (
    download_and_extract,
    find_grafana_binary,
    get_binaries,
    get_binary_path,
)
from lokikit.logging import get_logger
from lokikit.process import (
    check_services_running,
    read_pid_file,
    start_process,
    stop_services,
    wait_for_services,
    write_pid_file,
)


def setup_command(ctx):
    """Download binaries and write config files."""
    base_dir = ctx.obj["BASE_DIR"]
    host = ctx.obj["HOST"]
    ctx.obj["GRAFANA_PORT"]
    loki_port = ctx.obj["LOKI_PORT"]
    promtail_port = ctx.obj["PROMTAIL_PORT"]
    config = ctx.obj["CONFIG"]

    logger = get_logger()

    ensure_dir(base_dir)
    binaries = get_binaries(base_dir)
    logger.info(f"Using Loki/Promtail version: {binaries['loki']['version']}")
    logger.info(f"Using Grafana version: {binaries['grafana']['version']}")

    # Loki and Promtail
    for name in ["loki", "promtail"]:
        bin_path = os.path.join(base_dir, binaries[name]["binary"])
        if os.path.exists(bin_path):
            logger.info(
                f"{name.capitalize()} binary already exists at {bin_path}, skipping download."
            )
        else:
            logger.info(f"Downloading {name}...")
            download_and_extract(binaries[name]["url"], base_dir, binaries[name]["filename"])
            if binaries["os_name"] != "windows":
                os.chmod(bin_path, 0o755)
            logger.info(f"{name.capitalize()} binary downloaded and extracted.")

    # Grafana
    grafana_bin = find_grafana_binary(
        base_dir, binaries["grafana"]["binary_name"], binaries["grafana"]["version"]
    )

    if grafana_bin and os.path.exists(grafana_bin):
        logger.info(f"Grafana binary already exists at {grafana_bin}, skipping download.")
    else:
        logger.info("Downloading Grafana...")
        download_and_extract(binaries["grafana"]["url"], base_dir, binaries["grafana"]["filename"])
        grafana_bin = find_grafana_binary(
            base_dir, binaries["grafana"]["binary_name"], binaries["grafana"]["version"]
        )

        if grafana_bin:
            if binaries["os_name"] != "windows":
                os.chmod(grafana_bin, 0o755)
            logger.info("Grafana downloaded and extracted.")
        else:
            logger.warning("Could not find grafana-server binary after extraction.")

    # Generate configs with the specified host and ports
    loki_config = LOKI_CONFIG_TEMPLATE.format(host=host, loki_port=loki_port)

    # Get custom Promtail configuration if specified
    promtail_config = PROMTAIL_CONFIG_TEMPLATE.format(
        host=host, loki_port=loki_port, promtail_port=promtail_port
    )

    # Default list of log paths - add lokikit logs directory
    default_log_paths = [
        {
            "path": os.path.join(base_dir, "logs", "*.log"),
            "job": "service_logs",
            "labels": {"source": "lokikit", "type": "service_log"},
        },
        {
            "path": os.path.join(base_dir, "logs", "lokikit_*.log"),
            "job": "lokikit_app",
            "labels": {"source": "lokikit", "type": "application_log"},
        },
    ]

    # Apply custom log paths if specified in config
    if "promtail" in config and "log_paths" in config["promtail"]:
        # Use both default and user-specified log paths
        log_paths = default_log_paths + config["promtail"]["log_paths"]
    else:
        # Use only default log paths
        log_paths = default_log_paths

    # Create a modified promtail config with custom log paths
    custom_targets = []
    for i, log_path in enumerate(log_paths):
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
        logger.debug(f"Added log path: {path} with job: {job}")

    # Replace the default scrape_config with our custom ones
    if custom_targets:
        base_config = f"""server:
  http_listen_port: {promtail_port}
  http_listen_address: {host}
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://{host}:{loki_port}/loki/api/v1/push

scrape_configs:"""

        promtail_config = base_config + "".join(custom_targets)
        logger.info("Using custom log paths configuration.")

    # Write config files
    logger.debug("Writing Loki configuration...")
    write_config(os.path.join(base_dir, "loki-config.yaml"), loki_config)
    logger.debug("Writing Promtail configuration...")
    write_config(os.path.join(base_dir, "promtail-config.yaml"), promtail_config)

    # Create Grafana provisioning directories for datasource
    if grafana_bin:
        grafana_home = os.path.dirname(os.path.dirname(grafana_bin))
        grafana_provisioning_dir = os.path.join(grafana_home, "conf", "provisioning")
        grafana_datasources_dir = os.path.join(grafana_provisioning_dir, "datasources")
        ensure_dir(grafana_datasources_dir)

        # Check if Loki datasource config already exists
        loki_ds_config_path = os.path.join(grafana_datasources_dir, "lokikit.yaml")
        if not os.path.exists(loki_ds_config_path):
            # Create Loki datasource provisioning config
            loki_datasource_config = {
                "apiVersion": 1,
                "datasources": [
                    {
                        "name": "lokikit",
                        "type": "loki",
                        "access": "proxy",
                        "url": f"http://{host}:{loki_port}",
                        "isDefault": True,
                        "jsonData": {"maxLines": 1000, "timeout": 60},
                    }
                ],
            }

            # Write datasource config
            with open(loki_ds_config_path, "w") as f:
                yaml.dump(loki_datasource_config, f, default_flow_style=False)

            logger.info(
                f"Created Loki datasource configuration for Grafana at {loki_ds_config_path}"
            )
        else:
            logger.debug(f"Loki datasource configuration already exists at {loki_ds_config_path}")

    logger.info("Setup complete.")


def start_command(ctx, background, force, timeout):
    """Start Loki, Promtail, and Grafana."""
    base_dir = ctx.obj["BASE_DIR"]
    host = ctx.obj["HOST"]
    grafana_port = ctx.obj["GRAFANA_PORT"]
    loki_port = ctx.obj["LOKI_PORT"]
    promtail_port = ctx.obj["PROMTAIL_PORT"]

    logger = get_logger()
    logger.debug(
        "Starting services with: host=%s, loki=%s, promtail=%s, grafana=%s",
        host,
        loki_port,
        promtail_port,
        grafana_port,
    )

    # Check if services are already running
    existing_pids = read_pid_file(base_dir)
    if existing_pids and check_services_running(existing_pids) and not force:
        logger.info(f"Services are already running with PIDs: {existing_pids}")
        logger.info(f"- Grafana: http://{host}:{grafana_port}")
        logger.info("  (Default credentials: admin/admin)")
        logger.info(f"- Loki API: http://{host}:{loki_port}/loki/api/v1/labels")
        logger.info("  (Loki has no UI - access through Grafana or use API endpoints)")
        logger.info(f"- Promtail: http://{host}:{promtail_port}")
        logger.info("Use --force to start anyway.")
        if not background:
            logger.info(
                "Press Ctrl+C to exit or run 'lokikit stop' from another terminal to stop the services."
            )
            try:
                import signal

                signal.pause()
            except KeyboardInterrupt:
                logger.info("Exiting without stopping services. Run 'lokikit stop' to stop them.")
        return

    # Stop existing services if forcing
    if existing_pids and force:
        logger.info("Stopping existing services first...")
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
        if not loki_bin:
            missing.append("loki")
        if not promtail_bin:
            missing.append("promtail")
        if not grafana_bin:
            missing.append("grafana")
        logger.error(f"Missing binaries {', '.join(missing)}. Please run 'lokikit setup' first.")
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
    logger.debug(f"Starting Loki with config: {loki_cfg}")
    procs["loki"] = start_process([loki_bin, "-config.file", loki_cfg], loki_log)

    # Start Promtail
    promtail_log = os.path.join(logs_dir, "promtail.log")
    logger.debug(f"Starting Promtail with config: {promtail_cfg}")
    procs["promtail"] = start_process([promtail_bin, "-config.file", promtail_cfg], promtail_log)

    # Start Grafana
    grafana_log = os.path.join(logs_dir, "grafana.log")
    grafana_home = os.path.dirname(os.path.dirname(grafana_bin))

    # Ensure Grafana provisioning directories exist
    grafana_provisioning_dir = os.path.join(grafana_home, "conf", "provisioning")
    grafana_datasources_dir = os.path.join(grafana_provisioning_dir, "datasources")
    ensure_dir(grafana_datasources_dir)

    # Check if Loki datasource config already exists
    loki_ds_config_path = os.path.join(grafana_datasources_dir, "lokikit.yaml")
    if not os.path.exists(loki_ds_config_path):
        # Create Loki datasource provisioning config
        loki_datasource_config = {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "lokikit",
                    "type": "loki",
                    "access": "proxy",
                    "url": f"http://{host}:{loki_port}",
                    "isDefault": True,
                    "jsonData": {"maxLines": 1000, "timeout": 60},
                }
            ],
        }

        # Write datasource config
        with open(loki_ds_config_path, "w") as f:
            yaml.dump(loki_datasource_config, f, default_flow_style=False)

        logger.info(f"Created Loki datasource configuration for Grafana at {loki_ds_config_path}")
    else:
        logger.debug(f"Loki datasource configuration already exists at {loki_ds_config_path}")

    # Use the classic grafana-server format
    grafana_cmd = [
        grafana_bin,
        "--homepath",
        grafana_home,
        "--config",
        os.path.join(grafana_home, "conf/defaults.ini"),
        "--configOverrides",
        f"server.http_addr={host};server.http_port={grafana_port}",
    ]

    logger.debug(f"Starting Grafana with command: {' '.join(grafana_cmd)}")
    procs["grafana"] = start_process(grafana_cmd, grafana_log)

    # Wait for services to start
    ports = {"loki": loki_port, "promtail": promtail_port, "grafana": grafana_port}
    wait_for_services(host, ports, procs, timeout)

    # Store process IDs for background mode and potential future operations
    pids = {name: proc.pid for name, proc in procs.items()}
    pid_file = write_pid_file(pids, base_dir)
    logger.debug(f"Wrote PID file with PIDs: {pids}")

    logger.info("\nAll services started:")
    logger.info(f"- Grafana: http://{host}:{grafana_port}")
    logger.info("  (Default credentials: admin/admin)")
    logger.info(f"- Loki API: http://{host}:{loki_port}/loki/api/v1/labels")
    logger.info("  (Loki has no UI - access through Grafana or use API endpoints)")
    logger.info(f"- Promtail: http://{host}:{promtail_port}")
    logger.info(f"Log files are located in: {logs_dir}")

    if background:
        logger.info(f"Running in background mode. PIDs stored in {pid_file}")
        logger.info("To check status: lokikit status")
        logger.info("To stop the services: lokikit stop")
        return
    logger.info("\nPress Ctrl+C to stop the services.")
    try:
        # In foreground mode, wait for all processes
        # This keeps the process running in the foreground
        while all(proc.poll() is None for proc in procs.values()):
            import time

            time.sleep(1)

        # If we get here, at least one process has terminated
        logger.warning("One or more services have terminated unexpectedly.")
        for name, proc in procs.items():
            if proc.poll() is not None:
                logger.warning(f"- {name} exited with code {proc.poll()}")
        logger.info(f"Check the log files in {logs_dir} for details.")

    except KeyboardInterrupt:
        logger.info("\nStopping services...")
        for name, proc in procs.items():
            try:
                proc.terminate()
                logger.info(f"Terminated {name}")
            except:
                pass


def stop_command(ctx, force):
    """Stop running services."""
    base_dir = ctx.obj["BASE_DIR"]
    logger = get_logger()

    logger.debug("Stopping lokikit services...")

    # First try to stop using PID file
    pids = read_pid_file(base_dir)
    services_stopped = False

    if pids:
        services_stopped = stop_services(pids, force=force)
        if not services_stopped:
            logger.error(
                "Failed to stop one or more services. Try using --force to terminate them."
            )
    else:
        logger.warning("No PID file found, searching for running processes by pattern...")

    # Even if PID file doesn't exist, try to find and kill processes by pattern
    if not pids or not services_stopped:
        # Try to identify processes by pattern
        found_processes = False
        for name, pattern in [
            ("loki", "loki-.*"),
            ("promtail", "promtail-.*"),
            ("grafana", "grafana-server"),
        ]:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", pattern], capture_output=True, text=True, check=False
                )
                if result.returncode == 0 and result.stdout.strip():
                    found_processes = True
                    pids_found = [int(pid) for pid in result.stdout.strip().split()]
                    logger.info(f"Found {name} processes: {pids_found}")

                    for pid in pids_found:
                        try:
                            if force:
                                logger.info(f"Force killing {name} (PID: {pid})...")
                                os.kill(pid, signal.SIGKILL)
                            else:
                                logger.info(f"Stopping {name} (PID: {pid})...")
                                os.kill(pid, signal.SIGTERM)
                                # Wait for termination
                                for _ in range(10):
                                    try:
                                        os.kill(pid, 0)
                                        time.sleep(0.1)
                                    except OSError:
                                        break
                                else:
                                    # Still running, try SIGKILL
                                    logger.warning("Process did not terminate, using SIGKILL...")
                                    os.kill(pid, signal.SIGKILL)
                        except OSError as e:
                            logger.error(f"Error stopping {name} (PID: {pid}): {e}")
            except subprocess.SubprocessError as e:
                logger.error(f"Error searching for {name} processes: {e}")

        if not found_processes:
            logger.info("No running lokikit processes found.")

    # Remove PID file if it exists
    pid_file = os.path.join(base_dir, "lokikit.pid")
    if os.path.exists(pid_file):
        try:
            os.remove(pid_file)
            logger.info("Removed PID file.")
        except OSError as e:
            logger.error(f"Failed to remove PID file: {e}")

    logger.info("Operation completed.")


def status_command(ctx):
    """Check if services are running."""
    base_dir = ctx.obj["BASE_DIR"]
    host = ctx.obj["HOST"]
    grafana_port = ctx.obj["GRAFANA_PORT"]
    loki_port = ctx.obj["LOKI_PORT"]
    promtail_port = ctx.obj["PROMTAIL_PORT"]
    import subprocess

    logger = get_logger()
    logger.debug("Checking status of lokikit services...")

    # First try to get status from PID file
    pids = read_pid_file(base_dir)
    running_from_pid = False

    if pids:
        running_from_pid = check_services_running(pids)

    # Even if PID file doesn't exist or PIDs are no longer valid,
    # check for running processes by pattern
    running_services = {}

    for name, pattern in [
        ("loki", "loki-.*"),
        ("promtail", "promtail-.*"),
        ("grafana", "grafana-server"),
    ]:
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern], capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                # Store the PIDs found
                running_services[name] = [int(pid) for pid in result.stdout.strip().split()]
        except subprocess.SubprocessError:
            pass

    if running_from_pid:
        logger.info("Services are running according to PID file:")
        for name, pid in pids.items():
            logger.info(f"- {name.capitalize()}: PID {pid}")
    elif running_services:
        logger.info("Services are running but the PID file may be out of sync:")
        for name, pids_list in running_services.items():
            logger.info(f"- {name.capitalize()}: PIDs {', '.join(map(str, pids_list))}")
        logger.info(
            "\nConsider running 'lokikit stop' and then 'lokikit start' to synchronize the PID file."
        )
    else:
        logger.info("No services appear to be running.")
        return

    # If any services are running, show the access URLs
    if running_from_pid or running_services:
        logger.info("\nAccess URLs:")
        logger.info(f"- Grafana: http://{host}:{grafana_port}")
        logger.info("  (Default credentials: admin/admin)")
        logger.info(f"- Loki API: http://{host}:{loki_port}/loki/api/v1/labels")
        logger.info("  (Loki has no UI - access through Grafana or use API endpoints)")
        logger.info(f"- Promtail: http://{host}:{promtail_port}")


def clean_command(ctx):
    """Remove all downloaded files and configs."""
    base_dir = ctx.obj["BASE_DIR"]
    logger = get_logger()

    logger.debug(f"Cleaning up lokikit files from {base_dir}...")

    # Check if services are running and stop them first
    pids = read_pid_file(base_dir)
    if pids and check_services_running(pids):
        logger.warning("Services are still running. Please stop them first using 'lokikit stop'.")
        logger.info("Operation aborted.")
        sys.exit(1)

    if os.path.exists(base_dir):
        try:
            shutil.rmtree(base_dir)
            logger.info("Cleaned up all files.")
        except OSError as e:
            logger.error(f"Failed to remove directory: {e}")
            sys.exit(1)
    else:
        logger.info(f"Nothing to clean: directory {base_dir} does not exist.")


def watch_command(ctx, path, job, label):
    """Add a log path to Promtail configuration."""
    base_dir = ctx.obj["BASE_DIR"]
    logger = get_logger()

    logger.debug(f"Adding log path '{path}' with job '{job}' to Promtail config...")

    # Parse labels
    labels = {}
    if label:  # Check if label is not None before iterating
        for lbl in label:
            try:
                key, value = lbl.split("=", 1)
                labels[key.strip()] = value.strip()
            except ValueError:
                logger.warning(f"Ignoring invalid label format: {lbl}. Use key=value format.")

    # Update promtail config
    if update_promtail_config(base_dir, path, job, labels):
        # Check if services are running
        pids = read_pid_file(base_dir)
        if pids and check_services_running(pids):
            logger.info("\nServices are currently running.")
            logger.info("To apply changes, restart services with: lokikit stop && lokikit start")
    else:
        logger.info("No changes made to Promtail configuration.")


def force_quit_command(ctx):
    """Forcefully terminate all lokikit processes including stale ones.

    This is useful when the PID file is out of sync with actual running processes,
    or when processes remain after abnormal termination.
    """
    base_dir = ctx.obj["BASE_DIR"]
    logger = get_logger()

    logger.info("Force-quitting all lokikit processes...")

    # Step 1: Check PID file and kill those processes
    pid_file = os.path.join(base_dir, "lokikit.pid")
    if os.path.exists(pid_file):
        pids = read_pid_file(base_dir)
        if pids:
            logger.info("Found PID file with the following processes:")
            for name, pid in pids.items():
                try:
                    logger.info(f"Killing {name} (PID: {pid}) with SIGKILL...")
                    os.kill(pid, signal.SIGKILL)
                except OSError as e:
                    if e.errno == 3:  # No such process
                        logger.info(f"Process {name} (PID: {pid}) was not running")
                    else:
                        logger.error(f"Error killing {name}: {e}")

        # Remove the PID file
        try:
            os.remove(pid_file)
            logger.info("Removed PID file")
        except OSError as e:
            logger.error(f"Error removing PID file: {e}")
    else:
        logger.info("No PID file found")

    # Step 2: Find all related processes by pattern and kill them
    service_patterns = [
        ("loki", "loki-.*"),
        ("promtail", "promtail-.*"),
        ("grafana", "grafana-server.*"),
    ]

    for name, pattern in service_patterns:
        killed_pids = []
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern], capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                pids_found = [int(pid) for pid in result.stdout.strip().split()]
                if pids_found:
                    logger.info(f"Found {name} processes: {pids_found}")

                    for pid in pids_found:
                        try:
                            logger.info(f"Force killing {name} (PID: {pid})...")
                            os.kill(pid, signal.SIGKILL)
                            killed_pids.append(pid)
                        except OSError as e:
                            logger.error(f"Error killing {name} (PID: {pid}): {e}")

            if killed_pids:
                logger.info(f"Killed {name} processes with PIDs: {killed_pids}")
            else:
                logger.info(f"No running {name} processes found")

        except subprocess.SubprocessError as e:
            logger.error(f"Error searching for {name} processes: {e}")

    # Step 3: Create a fresh state
    logger.info("All lokikit processes have been terminated")
    logger.info("You can now start services with a clean state using: lokikit start")
