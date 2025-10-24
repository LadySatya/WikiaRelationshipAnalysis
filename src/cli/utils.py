"""
Shared utilities for CLI commands.
"""

import logging
from pathlib import Path
from typing import Dict, Any
import yaml


def setup_project_logging(project_name: str, phase_name: str) -> logging.Logger:
    """
    Setup logging for a specific project and phase.

    Args:
        project_name: Name of the project
        phase_name: Name of the phase (e.g., "indexing", "discovery")

    Returns:
        Configured logger instance
    """
    # Create log directory
    log_dir = Path(f"data/projects/{project_name}/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create log file with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pipeline_{timestamp}.log"

    # Configure logger
    logger = logging.getLogger(f"wikia_analyzer.{project_name}")
    logger.setLevel(logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized. Log file: {log_file}")
    logger.info("=" * 80)
    logger.info(f"AVATAR WIKI POC - {phase_name.upper()}")
    logger.info("=" * 80)

    return logger


def load_crawler_config() -> Dict[str, Any]:
    """
    Load crawler configuration from YAML file.

    Returns:
        Dictionary with crawler configuration
    """
    config_path = Path("config/crawler_config.yaml")
    with open(config_path, 'r') as f:
        full_config = yaml.safe_load(f)

    return {
        'respect_robots_txt': full_config['crawler']['respect_robots_txt'],
        'user_agent': full_config['crawler']['user_agent'],
        'default_delay_seconds': full_config['crawler']['default_delay_seconds'],
        'target_namespaces': full_config['crawler']['target_namespaces'],
        'timeout_seconds': full_config['crawler']['timeout_seconds'],
        'max_retries': full_config['crawler']['max_retries'],
        'exclude_patterns': full_config['crawler']['exclude_patterns'],
        'save_state_every_n_pages': full_config['crawler']['save_state_every_n_pages'],
    }


def validate_project_exists(project_name: str, require_crawled: bool = False) -> Path:
    """
    Validate that a project exists and optionally that it has crawled data.

    Args:
        project_name: Name of the project
        require_crawled: Whether to require crawled pages

    Returns:
        Path to the project directory

    Raises:
        FileNotFoundError: If project doesn't exist or lacks required data
    """
    project_path = Path(f"data/projects/{project_name}")

    if not project_path.exists():
        raise FileNotFoundError(
            f"Project '{project_name}' not found. "
            f"Run 'python main.py crawl {project_name} <url>' first."
        )

    if require_crawled:
        processed_dir = project_path / "processed"
        if not processed_dir.exists() or not list(processed_dir.glob("*.json")):
            raise FileNotFoundError(
                f"No crawled pages found for project '{project_name}'. "
                f"Run 'python main.py crawl {project_name} <url>' first."
            )

    return project_path
