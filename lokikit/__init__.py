"""Lokikit: A minimal CLI to set up and run a local Loki+Promtail+Grafana stack."""

__version__ = "0.1.0"

from lokikit.cli import cli

__all__ = ["cli"]
