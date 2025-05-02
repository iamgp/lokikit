import os
import shutil
import subprocess
import urllib.request
import zipfile
import tarfile
import platform
import sys
import json
import click

DEFAULT_BASE_DIR = os.path.expanduser("~/.lokikit")

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
    else:
        loki_bin = f"loki-{loki_os}-{arch}"
        promtail_bin = f"promtail-{loki_os}-{arch}"

    if os_name == "windows":
        grafana_bin = f"grafana-{grafana_version}/bin/grafana-server.exe"
    else:
        grafana_bin = f"grafana-{grafana_version}/bin/grafana-server"

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
            "binary": grafana_bin,
            "version": grafana_version,
        },
        "os_name": os_name,
    }

LOKI_CONFIG = """auth_enabled: false
server:
  http_listen_port: 3100
ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 5m
  chunk_retain_period: 30s
  max_transfer_retries: 0
schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h
storage_config:
  boltdb_shipper:
    active_index_directory: /tmp/loki/index
    cache_location: /tmp/loki/cache
    shared_store: filesystem
  filesystem:
    directory: /tmp/loki/chunks
limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
chunk_store_config:
  max_look_back_period: 0s
table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
"""

PROMTAIL_CONFIG = """server:
  http_listen_port: 9080
  grpc_listen_port: 0
positions:
  filename: /tmp/positions.yaml
clients:
  - url: http://localhost:3100/loki/api/v1/push
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

def get_binary_path(name, binaries, base_dir):
    return os.path.join(base_dir, binaries[name]["binary"])

def start_process(cmd, log_file):
    print(f"Starting: {' '.join(cmd)}")
    with open(log_file, "w") as f:
        return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)

@click.group()
@click.option(
    "--base-dir",
    default=DEFAULT_BASE_DIR,
    show_default=True,
    help="Base directory for downloads and configs.",
)
@click.pass_context
def cli(ctx, base_dir):
    """lokikit: Minimal Loki+Promtail+Grafana stack launcher."""
    ctx.ensure_object(dict)
    ctx.obj["BASE_DIR"] = os.path.expanduser(base_dir)

@cli.command()
@click.pass_context
def setup(ctx):
    """Download binaries and write config files."""
    base_dir = ctx.obj["BASE_DIR"]
    ensure_dir(base_dir)
    binaries = get_binaries(base_dir)
    print(f"Using Loki/Promtail version: {binaries['loki']['version']}")
    print(f"Using Grafana version: {binaries['grafana']['version']}")
    for name in ["loki", "promtail"]:
        bin_path = get_binary_path(name, binaries, base_dir)
        if os.path.exists(bin_path):
            print(f"{name.capitalize()} binary already exists at {bin_path}, skipping download.")
        else:
            download_and_extract(binaries[name]["url"], base_dir, binaries[name]["filename"])
            if binaries["os_name"] != "windows":
                os.chmod(bin_path, 0o755)
    # Grafana
    bin_path = get_binary_path("grafana", binaries, base_dir)
    if os.path.exists(bin_path):
        print(f"Grafana binary already exists at {bin_path}, skipping download.")
    else:
        download_and_extract(binaries["grafana"]["url"], base_dir, binaries["grafana"]["filename"])
        if binaries["os_name"] != "windows":
            os.chmod(bin_path, 0o755)
    # Always (re)write config files
    write_config(os.path.join(base_dir, "loki-config.yaml"), LOKI_CONFIG)
    write_config(os.path.join(base_dir, "promtail-config.yaml"), PROMTAIL_CONFIG)
    print("Setup complete.")

@cli.command()
@click.pass_context
def start(ctx):
    """Start Loki, Promtail, and Grafana."""
    base_dir = ctx.obj["BASE_DIR"]
    binaries = get_binaries(base_dir)
    loki_bin = get_binary_path("loki", binaries, base_dir)
    promtail_bin = get_binary_path("promtail", binaries, base_dir)
    grafana_bin = get_binary_path("grafana", binaries, base_dir)
    loki_cfg = os.path.join(base_dir, "loki-config.yaml")
    promtail_cfg = os.path.join(base_dir, "promtail-config.yaml")
    procs = []
    procs.append(start_process([loki_bin, "-config.file", loki_cfg], os.path.join(base_dir, "loki.log")))
    procs.append(start_process([promtail_bin, "-config.file", promtail_cfg], os.path.join(base_dir, "promtail.log")))
    if binaries["os_name"] == "windows":
        grafana_home = os.path.join(base_dir, f"grafana-{binaries['grafana']['version']}")
    else:
        grafana_home = os.path.dirname(os.path.dirname(grafana_bin))
    procs.append(start_process([grafana_bin, "--homepath", grafana_home], os.path.join(base_dir, "grafana.log")))
    print("All services started. Access Grafana at http://localhost:3000")
    print("Press Ctrl+C to stop.")
    try:
        for proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        print("Stopping services...")
        for proc in procs:
            proc.terminate()

@cli.command()
@click.pass_context
def clean(ctx):
    """Remove all downloaded files and configs."""
    base_dir = ctx.obj["BASE_DIR"]
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        print("Cleaned up all files.")
