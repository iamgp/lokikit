import os
import shutil
import subprocess
import urllib.request
import zipfile
import tarfile
import platform
import sys
import json
import glob
import signal
import time
import click
import socket

DEFAULT_BASE_DIR = os.path.expanduser("~/.lokikit")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_GRAFANA_PORT = 3000
DEFAULT_LOKI_PORT = 3100
DEFAULT_PROMTAIL_PORT = 9080

def detect_platform():
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    if system.startswith("linux"):
        os_name = "linux"
    elif system.startswith("darwin"):
        os_name = "darwin"
    elif system.startswith("windows"):
        os_name = "windows"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    return os_name, arch

def get_latest_loki_version():
    url = "https://api.github.com/repos/grafana/loki/releases/latest"
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp)
        return data["tag_name"].lstrip("v")

def get_latest_grafana_version():
    url = "https://api.github.com/repos/grafana/grafana/releases/latest"
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp)
        return data["tag_name"].lstrip("v")

def get_binaries(base_dir):
    os_name, arch = detect_platform()
    loki_version = get_latest_loki_version()
    grafana_version = get_latest_grafana_version()

    if os_name == "darwin":
        loki_ext = "zip"
        grafana_ext = "tar.gz"
        loki_os = "darwin"
        grafana_os = "darwin"
    elif os_name == "linux":
        loki_ext = "zip"
        grafana_ext = "tar.gz"
        loki_os = "linux"
        grafana_os = "linux"
    elif os_name == "windows":
        loki_ext = "zip"
        grafana_ext = "zip"
        loki_os = "windows"
        grafana_os = "windows"
    else:
        raise RuntimeError("Unsupported OS for binary download.")

    if os_name == "windows":
        loki_bin = f"loki-{loki_os}-{arch}.exe"
        promtail_bin = f"promtail-{loki_os}-{arch}.exe"
        grafana_bin_name = "grafana-server.exe"
    else:
        loki_bin = f"loki-{loki_os}-{arch}"
        promtail_bin = f"promtail-{loki_os}-{arch}"
        grafana_bin_name = "grafana-server"

    return {
        "loki": {
            "url": f"https://github.com/grafana/loki/releases/download/v{loki_version}/loki-{loki_os}-{arch}.{loki_ext}",
            "filename": f"loki-{loki_os}-{arch}.{loki_ext}",
            "binary": loki_bin,
            "version": loki_version,
        },
        "promtail": {
            "url": f"https://github.com/grafana/loki/releases/download/v{loki_version}/promtail-{loki_os}-{arch}.{loki_ext}",
            "filename": f"promtail-{loki_os}-{arch}.{loki_ext}",
            "binary": promtail_bin,
            "version": loki_version,
        },
        "grafana": {
            "url": f"https://dl.grafana.com/oss/release/grafana-{grafana_version}.{grafana_os}-{arch}.{grafana_ext}",
            "filename": f"grafana-{grafana_version}.{grafana_os}-{arch}.{grafana_ext}",
            "binary_name": grafana_bin_name,
            "version": grafana_version,
        },
        "os_name": os_name,
    }

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

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def download_and_extract(url, dest, filename):
    print(f"Downloading {url} ...")
    local_path = os.path.join(dest, filename)
    urllib.request.urlretrieve(url, local_path)
    print(f"Downloaded to {local_path}")
    if local_path.endswith(".zip"):
        with zipfile.ZipFile(local_path, "r") as zip_ref:
            zip_ref.extractall(dest)
    elif local_path.endswith(".tar.gz"):
        with tarfile.open(local_path, "r:gz") as tar_ref:
            tar_ref.extractall(dest)

def write_config(filename, content):
    with open(filename, "w") as f:
        f.write(content)

def find_grafana_binary(base_dir, binary_name, grafana_version):
    """Find the grafana-server binary after extraction."""
    # Try different version patterns
    potential_patterns = [
        f"grafana-{grafana_version}*/**/{binary_name}",  # Without v prefix
        f"grafana-v{grafana_version}*/**/{binary_name}", # With v prefix
        f"**/grafana-*{grafana_version}*/**/{binary_name}", # Any form
    ]

    # Search for the executable binary, not just any file named grafana-server
    for pattern in potential_patterns:
        full_pattern = os.path.join(base_dir, pattern)
        print(f"Searching with pattern: {full_pattern}")
        matches = glob.glob(full_pattern, recursive=True)

        # Filter out non-executable matches or script files
        executable_matches = []
        for match in matches:
            if os.path.isfile(match) and os.access(match, os.X_OK):
                # Skip files in packaging/deb, packaging/rpm, etc.
                if "packaging" not in match and not match.endswith(".sh"):
                    executable_matches.append(match)

        if executable_matches:
            # Prefer bin/grafana-server
            for match in executable_matches:
                if "/bin/" in match:
                    print(f"Found Grafana binary at: {match}")
                    return match

            # Otherwise return the first executable
            print(f"Found Grafana binary at: {executable_matches[0]}")
            return executable_matches[0]

    # If we can't find by glob, try a more direct search
    direct_paths = [
        os.path.join(base_dir, f"grafana-{grafana_version}/bin/{binary_name}"),
        os.path.join(base_dir, f"grafana-v{grafana_version}/bin/{binary_name}"),
    ]

    for path in direct_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            print(f"Found Grafana binary at direct path: {path}")
            return path

    # Last resort - use find command if available
    try:
        print("Attempting to find Grafana binary using find command...")
        result = subprocess.run(
            ["find", base_dir, "-name", binary_name, "-type", "f", "-executable"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            # Filter out packaging files
            binaries = [line for line in result.stdout.strip().split('\n')
                       if line and "packaging" not in line]
            if binaries:
                print(f"Found Grafana binary using find command: {binaries[0]}")
                return binaries[0]
    except (subprocess.SubprocessError, FileNotFoundError):
        # find command failed or not available
        pass

    print(f"Could not find Grafana binary {binary_name} in {base_dir}")
    return None

def get_binary_path(name, binaries, base_dir):
    """Get path to binary, with special handling for grafana."""
    if name in ["loki", "promtail"]:
        return os.path.join(base_dir, binaries[name]["binary"])
    elif name == "grafana":
        # For grafana, we need to find the binary after extraction
        return find_grafana_binary(
            base_dir,
            binaries["grafana"]["binary_name"],
            binaries["grafana"]["version"]
        )

def start_process(cmd, log_file):
    """Start a process and return the Popen object."""
    print(f"Starting: {' '.join(cmd)}")
    with open(log_file, "w") as f:
        return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)

def write_pid_file(pids, base_dir):
    """Write process IDs to a file for background mode."""
    pid_file = os.path.join(base_dir, "lokikit.pid")
    with open(pid_file, "w") as f:
        for name, pid in pids.items():
            f.write(f"{name}={pid}\n")
    print(f"Process IDs written to {pid_file}")
    return pid_file

def read_pid_file(base_dir):
    """Read process IDs from the PID file."""
    pid_file = os.path.join(base_dir, "lokikit.pid")
    if not os.path.exists(pid_file):
        return None

    pids = {}
    with open(pid_file, "r") as f:
        for line in f:
            if "=" in line:
                name, pid_str = line.strip().split("=", 1)
                try:
                    pids[name] = int(pid_str)
                except ValueError:
                    pass
    return pids

def check_services_running(pids):
    """Check if services with the given PIDs are running."""
    if not pids:
        return False

    # First try checking by PID
    for name, pid in pids.items():
        try:
            # Sending signal 0 checks if process exists
            os.kill(pid, 0)
        except OSError:
            # Process with that PID doesn't exist, try checking by pattern
            pattern = ""
            if name == "loki":
                pattern = "loki-.*-amd64"
            elif name == "promtail":
                pattern = "promtail-.*-amd64"
            elif name == "grafana":
                pattern = "grafana"

            if pattern:
                # Try to find by pattern
                try:
                    result = subprocess.run(
                        ["pgrep", "-f", pattern],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        # Found a match, pick the first one
                        pids[name] = int(result.stdout.split()[0])
                        continue
                except (subprocess.SubprocessError, ValueError, IndexError):
                    pass

            # Neither PID nor pattern search found a match
            return False

    return True

def service_is_accessible(host, port, timeout=0.5):
    """Check if a service is accessible on the given host and port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, int(port)))
        s.close()
        return True
    except (socket.error, ValueError):
        return False

def wait_for_services(host, ports, procs, timeout=20):
    """Wait for services to start up properly.

    Args:
        host: Host address to check
        ports: Dictionary mapping service names to ports
        procs: Dictionary of process objects
        timeout: Maximum time to wait in seconds

    Returns:
        True if all services started, False otherwise
    """
    start_time = time.time()
    all_ready = False
    statuses = {name: {"ready": False} for name in ports.keys()}

    print("Waiting for services to start...")

    while time.time() - start_time < timeout:
        any_failed = False

        # Check if any processes terminated
        for name, proc in procs.items():
            if proc.poll() is not None:
                returncode = proc.poll()
                print(f"Error: {name} process terminated with exit code {returncode}")
                any_failed = True

        if any_failed:
            return False

        # Check service accessibility
        for name, port in ports.items():
            check_host = "127.0.0.1" if host == "0.0.0.0" else host
            if service_is_accessible(check_host, port):
                if not statuses[name]["ready"]:
                    print(f"✓ {name.capitalize()} is ready on port {port}")
                    statuses[name]["ready"] = True

        # Check if all services are ready
        all_ready = all(status["ready"] for status in statuses.values())
        if all_ready:
            print("All services are ready!")
            return True

        # Wait a bit before checking again
        time.sleep(1)

    # If we got here, we timed out
    print(f"Timed out after {timeout} seconds waiting for services to start.")
    ready_services = [name for name, status in statuses.items() if status["ready"]]
    not_ready = [name for name, status in statuses.items() if not status["ready"]]

    if ready_services:
        print(f"Services that are ready: {', '.join(ready_services)}")
    if not_ready:
        print(f"Services that failed to start: {', '.join(not_ready)}")

    return False

@click.group()
@click.option(
    "--base-dir",
    default=DEFAULT_BASE_DIR,
    show_default=True,
    help="Base directory for downloads and configs.",
)
@click.option(
    "--host",
    default=DEFAULT_HOST,
    show_default=True,
    help="Host address to bind services to (e.g., 0.0.0.0 for all interfaces).",
)
@click.option(
    "--port",
    default=DEFAULT_GRAFANA_PORT,
    show_default=True,
    help="Port for Grafana server.",
)
@click.option(
    "--loki-port",
    default=DEFAULT_LOKI_PORT,
    show_default=True,
    help="Port for Loki server.",
)
@click.option(
    "--promtail-port",
    default=DEFAULT_PROMTAIL_PORT,
    show_default=True,
    help="Port for Promtail server.",
)
@click.pass_context
def cli(ctx, base_dir, host, port, loki_port, promtail_port):
    """lokikit: Minimal Loki+Promtail+Grafana stack launcher."""
    ctx.ensure_object(dict)
    ctx.obj["BASE_DIR"] = os.path.expanduser(base_dir)
    ctx.obj["HOST"] = host
    ctx.obj["GRAFANA_PORT"] = port
    ctx.obj["LOKI_PORT"] = loki_port
    ctx.obj["PROMTAIL_PORT"] = promtail_port

@cli.command()
@click.pass_context
def setup(ctx):
    """Download binaries and write config files."""
    base_dir = ctx.obj["BASE_DIR"]
    host = ctx.obj["HOST"]
    grafana_port = ctx.obj["GRAFANA_PORT"]
    loki_port = ctx.obj["LOKI_PORT"]
    promtail_port = ctx.obj["PROMTAIL_PORT"]

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

    promtail_config = PROMTAIL_CONFIG_TEMPLATE.format(
        host=host,
        loki_port=loki_port,
        promtail_port=promtail_port
    )

    # Write config files
    write_config(os.path.join(base_dir, "loki-config.yaml"), loki_config)
    write_config(os.path.join(base_dir, "promtail-config.yaml"), promtail_config)
    print("Setup complete.")

@cli.command()
@click.option(
    "--background",
    is_flag=True,
    default=False,
    help="Run services in the background and return to terminal."
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force start even if services are already running."
)
@click.option(
    "--timeout",
    default=20,
    type=int,
    help="Maximum time to wait for services to start (in seconds)."
)
@click.pass_context
def start(ctx, background, force, timeout):
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
        print(f"- Loki: http://{host}:{loki_port}")
        print(f"- Promtail: http://{host}:{promtail_port}")
        print("Use --force to start anyway.")
        if not background:
            print("Press Ctrl+C to exit or run 'lokikit stop' from another terminal to stop the services.")
            try:
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
    print(f"- Loki: http://{host}:{loki_port}")
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

def stop_services(pids):
    """Stop running services by PIDs."""
    success = True
    stopped = []
    failed = []

    for name, pid in pids.items():
        try:
            print(f"Stopping {name} (PID: {pid})...")
            os.kill(pid, signal.SIGTERM)

            # Wait a bit to see if the process terminates
            for _ in range(10):  # Wait up to 1 second
                try:
                    # Check if process is still running
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except OSError:
                    # Process is no longer running
                    break

            # Check one last time
            try:
                os.kill(pid, 0)
                # If we get here, process is still running
                print(f"  Service {name} (PID: {pid}) did not terminate, trying SIGKILL...")
                os.kill(pid, signal.SIGKILL)
                failed.append(name)
                success = False
            except OSError:
                # Process is gone
                print(f"  Service {name} stopped successfully")
                stopped.append(name)
        except OSError as e:
            if e.errno == 3:  # No such process
                print(f"  Service {name} (PID: {pid}) was not running")
                stopped.append(name)
            else:
                print(f"  Error stopping {name}: {e}")
                failed.append(name)
                success = False

    if stopped:
        print(f"Successfully stopped: {', '.join(stopped)}")
    if failed:
        print(f"Failed to stop: {', '.join(failed)}")

    return success

@cli.command()
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Use SIGKILL to forcefully terminate services."
)
@click.pass_context
def stop(ctx, force):
    """Stop running services."""
    base_dir = ctx.obj["BASE_DIR"]
    pids = read_pid_file(base_dir)

    if not pids:
        print("No running services found.")
        return

    if force:
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

@cli.command()
@click.pass_context
def status(ctx):
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
        print(f"- Loki: http://{host}:{loki_port}")
        print(f"- Promtail: http://{host}:{promtail_port}")
    else:
        print("Services are not running or have crashed.")
        print("Check the log files or run 'lokikit start' to restart them.")

@cli.command()
@click.pass_context
def clean(ctx):
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
