"""Command-line interface for lokikit."""

import click

from lokikit.commands import (
    clean_command,
    force_quit_command,
    parse_command,
    setup_command,
    start_command,
    status_command,
    stop_command,
    watch_command,
)
from lokikit.config import (
    DEFAULT_BASE_DIR,
    DEFAULT_GRAFANA_PORT,
    DEFAULT_HOST,
    DEFAULT_LOKI_PORT,
    DEFAULT_PROMTAIL_PORT,
    load_config_file,
    merge_config,
)
from lokikit.logger import setup_logging


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
@click.option(
    "--config",
    default=None,
    help="Path to YAML configuration file to override default options.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging for debugging.",
)
@click.pass_context
def cli(ctx, base_dir, host, port, loki_port, promtail_port, config, verbose):
    """lokikit: Minimal Loki+Promtail+Grafana stack launcher."""
    ctx.ensure_object(dict)

    # Load config file if specified
    file_config = {}
    if config:
        file_config = load_config_file(config)

    # Merge CLI options with file config
    cli_options = {
        "base_dir": base_dir,
        "host": host,
        "grafana_port": port,
        "loki_port": loki_port,
        "promtail_port": promtail_port,
    }

    merged_config = merge_config(cli_options, file_config)

    # Set context values from merged config
    ctx.obj["BASE_DIR"] = merged_config.get("base_dir", DEFAULT_BASE_DIR)
    ctx.obj["HOST"] = merged_config.get("host", DEFAULT_HOST)
    ctx.obj["GRAFANA_PORT"] = merged_config.get("grafana_port", DEFAULT_GRAFANA_PORT)
    ctx.obj["LOKI_PORT"] = merged_config.get("loki_port", DEFAULT_LOKI_PORT)
    ctx.obj["PROMTAIL_PORT"] = merged_config.get("promtail_port", DEFAULT_PROMTAIL_PORT)
    ctx.obj["VERBOSE"] = verbose

    # Setup logging system
    logger = setup_logging(ctx.obj["BASE_DIR"], verbose)
    logger.debug("lokikit starting with config: %s", merged_config)

    # Store all config in context for commands to access
    ctx.obj["CONFIG"] = merged_config


@cli.command()
@click.pass_context
def setup(ctx):
    """Download binaries and write config files."""
    setup_command(ctx)


@cli.command()
@click.option(
    "--background",
    is_flag=True,
    default=False,
    help="Run services in the background and return to terminal.",
)
@click.option("--force", is_flag=True, default=False, help="Force start even if services are already running.")
@click.option(
    "--timeout",
    default=20,
    type=int,
    help="Maximum time to wait for services to start (in seconds).",
)
@click.pass_context
def start(ctx, background, force, timeout):
    """Start Loki, Promtail, and Grafana."""
    start_command(ctx, background, force, timeout)


@cli.command()
@click.option("--force", is_flag=True, default=False, help="Use SIGKILL to forcefully terminate services.")
@click.pass_context
def stop(ctx, force):
    """Stop running services."""
    stop_command(ctx, force)


@cli.command()
@click.pass_context
def status(ctx):
    """Check if services are running."""
    status_command(ctx)


@cli.command()
@click.pass_context
def clean(ctx):
    """Remove all downloaded files and configs."""
    clean_command(ctx)


@cli.command()
@click.argument("path")
@click.option("--job", help="Job name for the log path.")
@click.option("--label", multiple=True, help="Labels in format key=value. Can be specified multiple times.")
@click.pass_context
def watch(ctx, path, job, label):
    """Add a log path to Promtail configuration.

    PATH is the file or directory to watch for logs (glob patterns supported).
    """
    watch_command(ctx, path, job, label)


@cli.command(name="force-quit")
@click.pass_context
def force_quit(ctx):
    """Find and kill all lokikit processes, including stale ones not tracked by PID file.

    This resolves issues with stale processes and PID file mismatches.
    """
    force_quit_command(ctx)


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--dashboard-name", help="Name for the generated Grafana dashboard.")
@click.option("--max-files", type=int, default=5, help="Maximum number of log files to sample.")
@click.option("--max-lines", type=int, default=100, help="Maximum number of lines to sample per file.")
@click.pass_context
def parse(ctx, directory, dashboard_name, max_files, max_lines):
    """Parse logs and interactively create Grafana dashboards.

    DIRECTORY is the directory containing log files to parse.
    """
    parse_command(ctx, directory, dashboard_name, max_files, max_lines)


if __name__ == "__main__":
    cli()
