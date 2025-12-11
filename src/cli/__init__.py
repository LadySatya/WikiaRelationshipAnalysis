"""
CLI command handlers for WikiaAnalyzer.

This module provides command-line interface functionality for all phases
of the WikiaAnalyzer pipeline.
"""

from .crawl_commands import crawl_command, resume_command
from .pipeline import pipeline_command, validate_command
from .processor_commands import discover_command, index_command
from .utils import load_crawler_config, setup_project_logging

__all__ = [
    # Crawl commands (Phase 1)
    "crawl_command",
    "resume_command",
    # Processor commands (Phase 2)
    "index_command",
    "discover_command",
    # Meta commands
    "pipeline_command",
    "validate_command",
    # Utilities
    "setup_project_logging",
    "load_crawler_config",
]
