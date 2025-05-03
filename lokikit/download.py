"""Download module for lokikit."""

import glob
import json
import os
import platform
import subprocess
import tarfile
import urllib.request
import zipfile


def detect_platform():
    """Detect the current operating system and architecture."""
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
    """Get the latest Loki version from GitHub API."""
    url = "https://api.github.com/repos/grafana/loki/releases/latest"
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp)
        return data["tag_name"].lstrip("v")


def get_latest_grafana_version():
    """Get the latest Grafana version from GitHub API."""
    url = "https://api.github.com/repos/grafana/grafana/releases/latest"
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp)
        return data["tag_name"].lstrip("v")


def get_binaries(base_dir):
    """Get download URLs and paths for binaries."""
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


def download_and_extract(url, dest, filename):
    """Download and extract a binary archive."""
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


def find_grafana_binary(base_dir, binary_name, grafana_version):
    """Find the grafana-server binary after extraction."""
    # Try different version patterns
    potential_patterns = [
        f"grafana-{grafana_version}*/**/{binary_name}",  # Without v prefix
        f"grafana-v{grafana_version}*/**/{binary_name}",  # With v prefix
        f"**/grafana-*{grafana_version}*/**/{binary_name}",  # Any form
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
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Filter out packaging files
            binaries = [
                line
                for line in result.stdout.strip().split("\n")
                if line and "packaging" not in line
            ]
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
    if name == "grafana":
        # For grafana, we need to find the binary after extraction
        return find_grafana_binary(
            base_dir, binaries["grafana"]["binary_name"], binaries["grafana"]["version"]
        )
    return None
