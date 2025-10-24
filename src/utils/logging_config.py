"""
Centralized logging configuration for WikiaAnalyzer pipeline.

Provides consistent logging across all modules with both console and file output.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple


def setup_project_logger(
    project_name: str,
    log_level: int = logging.INFO
) -> Tuple[logging.Logger, Path]:
    """
    Setup logger that writes to both console and file.

    Args:
        project_name: Name of the project
        log_level: Logging level (default: INFO)

    Returns:
        Tuple of (logger, log_file_path)
    """
    logger = logging.getLogger(f"wikia_analyzer.{project_name}")
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '[%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_format)

    # File handler (DEBUG and above)
    log_dir = Path("data") / "projects" / project_name / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pipeline_{timestamp}.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(f"Logging initialized. Log file: {log_file}")

    return logger, log_file
