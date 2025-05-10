"""
Utilities for managing Loki jobs in LokiKit.
"""

import logging
import os

import yaml

from lokikit.config import update_promtail_config


def ensure_job_exists(
    base_dir: str, job_name: str, log_path: str | None = None, labels: dict[str, str] | None = None
) -> bool:
    """
    Check if a job exists in Promtail configuration, and create it if it doesn't.

    Args:
        base_dir: Base directory for LokiKit
        job_name: Name of the job to check/create
        log_path: Optional path to logs for this job
        labels: Optional custom labels for the job

    Returns:
        bool: True if job exists or was created, False on error
    """
    logger = logging.getLogger("lokikit")

    # If no log path is provided, use a default one
    if not log_path:
        log_path = os.path.join(os.path.expanduser("~"), "logs", f"{job_name}/*.log")
        logger.debug(f"No log path provided, using default: {log_path}")

    # Ensure labels is a dictionary
    if labels is None:
        labels = {}

    # Check if job exists
    job_exists = job_exists_in_config(base_dir, job_name)

    if job_exists:
        logger.info(f"Job '{job_name}' already exists")
        return True

    # Job doesn't exist, create it
    logger.info(f"Creating job '{job_name}'")
    return update_promtail_config(base_dir, log_path, job_name, labels)


def job_exists_in_config(base_dir: str, job_name: str) -> bool:
    """
    Check if a job exists in the Promtail configuration.

    Args:
        base_dir: Base directory for LokiKit
        job_name: Name of the job to check

    Returns:
        bool: True if job exists, False otherwise
    """
    logger = logging.getLogger("lokikit")
    config_path = os.path.join(base_dir, "promtail-config.yaml")

    if not os.path.exists(config_path):
        logger.error(f"Promtail config not found at {config_path}")
        return False

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading Promtail config: {e}")
        return False

    # Check if job exists in scrape_configs
    if config and "scrape_configs" in config:
        for job in config["scrape_configs"]:
            if job.get("job_name") == job_name:
                return True

    return False


def get_all_jobs(base_dir: str) -> list[str]:
    """
    Get a list of all configured jobs in Promtail.

    Args:
        base_dir: Base directory for LokiKit

    Returns:
        List[str]: List of job names
    """
    logger = logging.getLogger("lokikit")
    config_path = os.path.join(base_dir, "promtail-config.yaml")
    jobs = []

    if not os.path.exists(config_path):
        logger.error(f"Promtail config not found at {config_path}")
        return jobs

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading Promtail config: {e}")
        return jobs

    # Extract job names from scrape_configs
    if config and "scrape_configs" in config:
        for job in config["scrape_configs"]:
            if "job_name" in job:
                jobs.append(job["job_name"])

    return jobs


def get_job_paths(base_dir: str, job_name: str) -> list[str]:
    """
    Get the log paths associated with a specific job.

    Args:
        base_dir: Base directory for LokiKit
        job_name: Name of the job to lookup

    Returns:
        List[str]: List of log paths for the job
    """
    logger = logging.getLogger("lokikit")
    config_path = os.path.join(base_dir, "promtail-config.yaml")
    paths = []

    if not os.path.exists(config_path):
        logger.error(f"Promtail config not found at {config_path}")
        return paths

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading Promtail config: {e}")
        return paths

    # Extract paths from the job configuration
    if config and "scrape_configs" in config:
        for job in config["scrape_configs"]:
            if job.get("job_name") == job_name:
                for static_config in job.get("static_configs", []):
                    if "__path__" in static_config.get("labels", {}):
                        paths.append(static_config["labels"]["__path__"])

    return paths


def get_job_names(base_dir: str) -> list[str]:
    """Get all job names from Promtail configuration.

    Args:
        base_dir: LokiKit base directory

    Returns:
        List of job names
    """
    # Path to promtail config
    config_path = os.path.join(base_dir, "promtail-config.yaml")

    # Check if config file exists
    if not os.path.exists(config_path):
        return []

    # Read existing config
    with open(config_path) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError:
            return []

    # Extract job names
    job_names = []
    if "scrape_configs" in config:
        for job_config in config["scrape_configs"]:
            job_name = job_config.get("job_name")
            if job_name:
                job_names.append(job_name)

    return job_names
