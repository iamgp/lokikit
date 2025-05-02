"""Process management module for lokikit."""

import os
import time
import signal
import socket
import subprocess

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
