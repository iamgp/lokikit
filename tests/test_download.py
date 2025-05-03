"""Tests for the LokiKit download module."""

import json
import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from lokikit.download import (
    detect_platform,
    download_and_extract,
    find_grafana_binary,
    get_binaries,
    get_binary_path,
    get_latest_grafana_version,
    get_latest_loki_version,
)


@patch("platform.system")
@patch("platform.machine")
def test_detect_linux_amd64(mock_machine, mock_system):
    """Test detecting Linux AMD64 platform."""
    mock_system.return_value = "Linux"
    mock_machine.return_value = "x86_64"

    os_name, arch = detect_platform()

    assert os_name == "linux"
    assert arch == "amd64"


@patch("platform.system")
@patch("platform.machine")
def test_detect_darwin_arm64(mock_machine, mock_system):
    """Test detecting macOS ARM64 platform."""
    mock_system.return_value = "Darwin"
    mock_machine.return_value = "arm64"

    os_name, arch = detect_platform()

    assert os_name == "darwin"
    assert arch == "arm64"


@patch("platform.system")
@patch("platform.machine")
def test_detect_windows_amd64(mock_machine, mock_system):
    """Test detecting Windows AMD64 platform."""
    mock_system.return_value = "Windows"
    mock_machine.return_value = "AMD64"

    os_name, arch = detect_platform()

    assert os_name == "windows"
    assert arch == "amd64"


@patch("platform.system")
@patch("platform.machine")
def test_detect_unsupported_os(mock_machine, mock_system):
    """Test detecting an unsupported OS."""
    mock_system.return_value = "FreeBSD"
    mock_machine.return_value = "x86_64"

    with pytest.raises(RuntimeError, match="Unsupported OS"):
        detect_platform()


@patch("platform.system")
@patch("platform.machine")
def test_detect_unsupported_arch(mock_machine, mock_system):
    """Test detecting an unsupported architecture."""
    mock_system.return_value = "Linux"
    mock_machine.return_value = "mips"

    with pytest.raises(RuntimeError, match="Unsupported architecture"):
        detect_platform()


@patch("urllib.request.urlopen")
def test_get_latest_loki_version(mock_urlopen):
    """Test retrieving the latest Loki version."""
    # Mock the API response
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = json.dumps({"tag_name": "v2.5.0"}).encode()
    mock_urlopen.return_value = mock_response

    version = get_latest_loki_version()

    assert version == "2.5.0"
    mock_urlopen.assert_called_with("https://api.github.com/repos/grafana/loki/releases/latest")


@patch("urllib.request.urlopen")
def test_get_latest_grafana_version(mock_urlopen):
    """Test retrieving the latest Grafana version."""
    # Mock the API response
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = json.dumps({"tag_name": "v9.0.0"}).encode()
    mock_urlopen.return_value = mock_response

    version = get_latest_grafana_version()

    assert version == "9.0.0"
    mock_urlopen.assert_called_with("https://api.github.com/repos/grafana/grafana/releases/latest")


@patch("lokikit.download.get_latest_grafana_version")
@patch("lokikit.download.get_latest_loki_version")
@patch("lokikit.download.detect_platform")
def test_get_binaries_linux(mock_detect_platform, mock_loki_version, mock_grafana_version):
    """Test getting binaries info for Linux."""
    mock_detect_platform.return_value = ("linux", "amd64")
    mock_loki_version.return_value = "2.5.0"
    mock_grafana_version.return_value = "9.0.0"

    base_dir = "/tmp/lokikit"
    binaries = get_binaries(base_dir)

    assert binaries["os_name"] == "linux"

    # Check Loki info
    assert binaries["loki"]["version"] == "2.5.0"
    assert binaries["loki"]["binary"] == "loki-linux-amd64"
    assert "loki-linux-amd64.zip" in binaries["loki"]["url"]

    # Check Promtail info
    assert binaries["promtail"]["version"] == "2.5.0"
    assert binaries["promtail"]["binary"] == "promtail-linux-amd64"
    assert "promtail-linux-amd64.zip" in binaries["promtail"]["url"]

    # Check Grafana info
    assert binaries["grafana"]["version"] == "9.0.0"
    assert binaries["grafana"]["binary_name"] == "grafana-server"
    assert "grafana-9.0.0.linux-amd64.tar.gz" in binaries["grafana"]["url"]


@patch("lokikit.download.get_latest_grafana_version")
@patch("lokikit.download.get_latest_loki_version")
@patch("lokikit.download.detect_platform")
def test_get_binaries_darwin(mock_detect_platform, mock_loki_version, mock_grafana_version):
    """Test getting binaries info for macOS."""
    mock_detect_platform.return_value = ("darwin", "arm64")
    mock_loki_version.return_value = "2.5.0"
    mock_grafana_version.return_value = "9.0.0"

    base_dir = "/tmp/lokikit"
    binaries = get_binaries(base_dir)

    assert binaries["os_name"] == "darwin"

    # Check Loki info
    assert binaries["loki"]["binary"] == "loki-darwin-arm64"
    assert "loki-darwin-arm64.zip" in binaries["loki"]["url"]

    # Check Promtail info
    assert binaries["promtail"]["binary"] == "promtail-darwin-arm64"
    assert "promtail-darwin-arm64.zip" in binaries["promtail"]["url"]

    # Check Grafana info
    assert binaries["grafana"]["binary_name"] == "grafana-server"
    assert "grafana-9.0.0.darwin-arm64.tar.gz" in binaries["grafana"]["url"]


@patch("lokikit.download.get_latest_grafana_version")
@patch("lokikit.download.get_latest_loki_version")
@patch("lokikit.download.detect_platform")
def test_get_binaries_windows(mock_detect_platform, mock_loki_version, mock_grafana_version):
    """Test getting binaries info for Windows."""
    mock_detect_platform.return_value = ("windows", "amd64")
    mock_loki_version.return_value = "2.5.0"
    mock_grafana_version.return_value = "9.0.0"

    base_dir = "/tmp/lokikit"
    binaries = get_binaries(base_dir)

    assert binaries["os_name"] == "windows"

    # Check Loki info
    assert binaries["loki"]["binary"] == "loki-windows-amd64.exe"
    assert "loki-windows-amd64.zip" in binaries["loki"]["url"]

    # Check Promtail info
    assert binaries["promtail"]["binary"] == "promtail-windows-amd64.exe"
    assert "promtail-windows-amd64.zip" in binaries["promtail"]["url"]

    # Check Grafana info
    assert binaries["grafana"]["binary_name"] == "grafana-server.exe"
    assert "grafana-9.0.0.windows-amd64.zip" in binaries["grafana"]["url"]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    # Clean up after tests
    os.rmdir(dir_path)


@patch("urllib.request.urlretrieve")
@patch("zipfile.ZipFile")
@patch("builtins.print")
def test_download_and_extract_zip(mock_print, mock_zipfile, mock_urlretrieve, temp_dir):
    """Test downloading and extracting a ZIP file."""
    url = "https://example.com/file.zip"
    filename = "file.zip"
    local_path = os.path.join(temp_dir, filename)

    # Mock the ZipFile context manager
    mock_zipfile_instance = MagicMock()
    mock_zipfile.return_value.__enter__.return_value = mock_zipfile_instance

    download_and_extract(url, temp_dir, filename)

    mock_urlretrieve.assert_called_once_with(url, local_path)
    mock_zipfile.assert_called_once_with(local_path, "r")
    mock_zipfile_instance.extractall.assert_called_once_with(temp_dir)
    assert mock_print.call_count == 2  # Should print download start and completion


@patch("urllib.request.urlretrieve")
@patch("tarfile.open")
@patch("builtins.print")
def test_download_and_extract_tar_gz(mock_print, mock_tarfile, mock_urlretrieve, temp_dir):
    """Test downloading and extracting a tar.gz file."""
    url = "https://example.com/file.tar.gz"
    filename = "file.tar.gz"
    local_path = os.path.join(temp_dir, filename)

    # Mock the tarfile context manager
    mock_tarfile_instance = MagicMock()
    mock_tarfile.return_value.__enter__.return_value = mock_tarfile_instance

    download_and_extract(url, temp_dir, filename)

    mock_urlretrieve.assert_called_once_with(url, local_path)
    mock_tarfile.assert_called_once_with(local_path, "r:gz")
    mock_tarfile_instance.extractall.assert_called_once_with(temp_dir)
    assert mock_print.call_count == 2  # Should print download start and completion


@pytest.fixture
def nested_temp_dir():
    """Create a temporary directory with nested structure for tests."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    # Clean up after tests - including nested files and directories
    for root, dirs, files in os.walk(dir_path, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            os.rmdir(os.path.join(root, dir))
    os.rmdir(dir_path)


@patch("glob.glob")
@patch("os.path.isfile")
@patch("os.access")
@patch("builtins.print")
def test_find_grafana_binary_by_glob(
    mock_print, mock_access, mock_isfile, mock_glob, nested_temp_dir
):
    """Test finding Grafana binary using glob pattern."""
    binary_name = "grafana-server"
    grafana_version = "9.0.0"

    # Mock the glob results
    binary_path = os.path.join(nested_temp_dir, f"grafana-{grafana_version}/bin/{binary_name}")
    mock_glob.return_value = [binary_path]

    # Mock the file checks
    mock_isfile.return_value = True
    mock_access.return_value = True

    result = find_grafana_binary(nested_temp_dir, binary_name, grafana_version)

    assert result == binary_path
    mock_glob.assert_called()
    mock_print.assert_called()


@patch("glob.glob")
@patch("os.path.isfile")
@patch("os.access")
@patch("builtins.print")
def test_find_grafana_binary_by_direct_path(
    mock_print, mock_access, mock_isfile, mock_glob, nested_temp_dir
):
    """Test finding Grafana binary using direct path."""
    binary_name = "grafana-server"
    grafana_version = "9.0.0"

    # Mock the glob results (no matches)
    mock_glob.return_value = []

    # Mock the file checks
    def mock_isfile_side_effect(path):
        return path == os.path.join(nested_temp_dir, f"grafana-{grafana_version}/bin/{binary_name}")

    def mock_access_side_effect(path, mode):
        return path == os.path.join(nested_temp_dir, f"grafana-{grafana_version}/bin/{binary_name}")

    mock_isfile.side_effect = mock_isfile_side_effect
    mock_access.side_effect = mock_access_side_effect

    result = find_grafana_binary(nested_temp_dir, binary_name, grafana_version)

    expected_path = os.path.join(nested_temp_dir, f"grafana-{grafana_version}/bin/{binary_name}")
    assert result == expected_path
    mock_glob.assert_called()
    mock_print.assert_called()


@patch("glob.glob")
@patch("os.path.isfile")
@patch("os.access")
@patch("subprocess.run")
@patch("builtins.print")
def test_find_grafana_binary_by_find_command(
    mock_print, mock_run, mock_access, mock_isfile, mock_glob, nested_temp_dir
):
    """Test finding Grafana binary using find command."""
    binary_name = "grafana-server"
    grafana_version = "9.0.0"

    # Mock the glob results (no matches)
    mock_glob.return_value = []

    # Mock the file checks (no direct path matches)
    mock_isfile.return_value = False
    mock_access.return_value = False

    # Mock the find command result
    binary_path = os.path.join(nested_temp_dir, f"grafana-{grafana_version}/bin/{binary_name}")
    mock_run.return_value = MagicMock(returncode=0, stdout=f"{binary_path}\n")

    result = find_grafana_binary(nested_temp_dir, binary_name, grafana_version)

    assert result == binary_path
    mock_glob.assert_called()
    mock_run.assert_called_once()
    mock_print.assert_called()


@patch("glob.glob")
@patch("os.path.isfile")
@patch("os.access")
@patch("subprocess.run")
@patch("builtins.print")
def test_find_grafana_binary_not_found(
    mock_print, mock_run, mock_access, mock_isfile, mock_glob, nested_temp_dir
):
    """Test when Grafana binary cannot be found."""
    binary_name = "grafana-server"
    grafana_version = "9.0.0"

    # Mock all search methods to fail
    mock_glob.return_value = []
    mock_isfile.return_value = False
    mock_access.return_value = False
    mock_run.side_effect = subprocess.SubprocessError()

    result = find_grafana_binary(nested_temp_dir, binary_name, grafana_version)

    assert result is None
    mock_glob.assert_called()
    mock_print.assert_called()


@pytest.fixture
def binary_info():
    """Create test binary info for tests."""
    return {
        "loki": {"binary": "loki-linux-amd64", "version": "2.5.0"},
        "promtail": {"binary": "promtail-linux-amd64", "version": "2.5.0"},
        "grafana": {"binary_name": "grafana-server", "version": "9.0.0"},
    }


def test_get_loki_binary_path(temp_dir, binary_info):
    """Test getting Loki binary path."""
    path = get_binary_path("loki", binary_info, temp_dir)
    expected_path = os.path.join(temp_dir, "loki-linux-amd64")
    assert path == expected_path


def test_get_promtail_binary_path(temp_dir, binary_info):
    """Test getting Promtail binary path."""
    path = get_binary_path("promtail", binary_info, temp_dir)
    expected_path = os.path.join(temp_dir, "promtail-linux-amd64")
    assert path == expected_path


@patch("lokikit.download.find_grafana_binary")
def test_get_grafana_binary_path(mock_find_grafana_binary, temp_dir, binary_info):
    """Test getting Grafana binary path."""
    expected_path = os.path.join(temp_dir, "grafana-9.0.0/bin/grafana-server")
    mock_find_grafana_binary.return_value = expected_path

    path = get_binary_path("grafana", binary_info, temp_dir)

    assert path == expected_path
    mock_find_grafana_binary.assert_called_once_with(temp_dir, "grafana-server", "9.0.0")
