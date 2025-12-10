"""
Centralized logging configuration for WikiaAnalysis.

Provides module-specific log files, LLM communication tracking,
and structured logging for easier debugging.

Log Structure:
    data/projects/<project>/logs/
    ├── main.log                    # Overall application log
    ├── crawler/
    │   ├── crawler.log             # Crawling operations
    │   ├── rate_limiting.log       # Rate limit, robots.txt, backoff
    │   └── extraction.log          # Page extraction, link discovery
    ├── processor/
    │   ├── processor.log           # General processing
    │   ├── character_discovery.log # Character extraction
    │   ├── profile_building.log    # Profile building
    │   └── rag.log                 # RAG pipeline (chunking, embedding, retrieval)
    ├── llm/
    │   ├── llm_calls.log           # High-level LLM call summaries
    │   ├── prompts.jsonl           # Full prompts for debugging (structured)
    │   └── tool_calls.jsonl        # Tool usage tracking (structured)
    └── errors.log                  # All errors across modules

Usage:
    from src.utils.logging_config import setup_logging, get_logger

    # Setup logging for a project (call once at startup)
    setup_logging(project_name="avatar", log_level="INFO")

    # Get module-specific logger
    logger = get_logger("crawler")
    logger.info("Started crawling https://avatar.fandom.com")

    # Get LLM logger for tracking API calls
    llm_logger = get_llm_logger()
    llm_logger.log_prompt(prompt="...", model="claude-sonnet-4")
"""

import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from logging.handlers import RotatingFileHandler


# Module-specific logger names
LOGGERS = {
    "main": "wikia.main",
    "crawler": "wikia.crawler",
    "crawler.rate_limiting": "wikia.crawler.rate_limiting",
    "crawler.extraction": "wikia.crawler.extraction",
    "processor": "wikia.processor",
    "processor.discovery": "wikia.processor.discovery",
    "processor.profiles": "wikia.processor.profiles",
    "processor.knowledge_builder": "wikia.processor.knowledge_builder",
    "processor.rag": "wikia.processor.rag",
    "llm": "wikia.llm",
    "llm.prompts": "wikia.llm.prompts",
    "llm.tools": "wikia.llm.tools",
}


class LLMLogger:
    """Specialized logger for LLM communication tracking."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.llm_dir = log_dir / "llm"
        self.llm_dir.mkdir(parents=True, exist_ok=True)

        # Standard logger for summaries
        self.logger = logging.getLogger(LOGGERS["llm"])

        # Structured log files
        self.prompts_file = self.llm_dir / "prompts.jsonl"
        self.tool_calls_file = self.llm_dir / "tool_calls.jsonl"

    def log_prompt(
        self,
        prompt: str,
        model: str,
        purpose: str,
        response: Optional[str] = None,
        usage: Optional[Dict[str, int]] = None,
        cost: Optional[float] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log an LLM prompt with structured data.

        Args:
            prompt: The prompt sent to LLM
            model: Model name (e.g., "claude-sonnet-4")
            purpose: What this prompt is for (e.g., "character_classification")
            response: LLM response (optional)
            usage: Token usage dict {"input_tokens": X, "output_tokens": Y}
            cost: Estimated cost in USD
            error: Error message if call failed
            metadata: Additional context
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "purpose": purpose,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "response_length": len(response) if response else 0,
            "response_preview": (response[:200] + "...") if response and len(response) > 200 else response,
            "usage": usage,
            "cost_usd": cost,
            "error": error,
            "metadata": metadata or {}
        }

        # Write structured log entry
        with open(self.prompts_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        # Log summary to standard log
        if error:
            self.logger.error(
                f"LLM call failed [{purpose}] model={model} error={error}"
            )
        else:
            tokens_str = f"tokens={usage['input_tokens']}+{usage['output_tokens']}" if usage else "tokens=unknown"
            cost_str = f"${cost:.4f}" if cost else "$?.??"
            self.logger.info(
                f"LLM call [{purpose}] model={model} {tokens_str} cost={cost_str}"
            )

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time_ms: Optional[float] = None
    ):
        """
        Log a tool call made by the LLM.

        Args:
            tool_name: Name of tool called
            tool_input: Input parameters to tool
            result: Tool execution result
            error: Error message if tool failed
            execution_time_ms: How long tool took to execute
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "input": tool_input,
            "result_summary": str(result)[:500] if result else None,
            "error": error,
            "execution_time_ms": execution_time_ms
        }

        # Write structured log entry
        with open(self.tool_calls_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        # Log summary
        if error:
            self.logger.error(
                f"Tool call failed: {tool_name}(**{list(tool_input.keys())}) error={error}"
            )
        else:
            time_str = f" ({execution_time_ms:.0f}ms)" if execution_time_ms else ""
            self.logger.info(
                f"Tool call: {tool_name}(**{list(tool_input.keys())}){time_str}"
            )


def setup_logging(
    project_name: str,
    log_level: str = "INFO",
    console_level: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> Path:
    """
    Setup logging configuration for a project.

    Args:
        project_name: Project name (e.g., "avatar")
        log_level: File log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_level: Console log level (defaults to log_level)
        max_bytes: Max size per log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Path to log directory
    """
    # Create log directory structure
    log_dir = Path("data") / "projects" / project_name / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (log_dir / "crawler").mkdir(exist_ok=True)
    (log_dir / "processor").mkdir(exist_ok=True)
    (log_dir / "llm").mkdir(exist_ok=True)

    # Convert log levels
    file_level = getattr(logging, log_level.upper())
    console_level = getattr(logging, (console_level or log_level).upper())

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_formatter = logging.Formatter(
        "%(levelname)-8s | %(name)-20s | %(message)s"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, filter at handler level

    # Remove existing handlers
    root_logger.handlers.clear()

    # Quiet down noisy third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Only show HTTP errors
    logging.getLogger("httpcore").setLevel(logging.WARNING)  # Only show connection errors
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Console handler (for active monitoring)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Main application log (everything)
    main_handler = RotatingFileHandler(
        log_dir / "main.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    main_handler.setLevel(file_level)
    main_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(main_handler)

    # Errors log (errors only, across all modules)
    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)

    # Module-specific handlers
    _setup_module_handlers(log_dir, file_level, detailed_formatter, max_bytes, backup_count)

    # Log startup
    logger = logging.getLogger(LOGGERS["main"])
    logger.info("=" * 80)
    logger.info(f"Logging initialized for project: {project_name}")
    logger.info(f"Log directory: {log_dir.absolute()}")
    logger.info(f"File log level: {log_level}, Console log level: {console_level or log_level}")
    logger.info("=" * 80)

    return log_dir


def _setup_module_handlers(
    log_dir: Path,
    level: int,
    formatter: logging.Formatter,
    max_bytes: int,
    backup_count: int
):
    """Setup file handlers for each module."""

    # Crawler logs
    _add_file_handler(
        LOGGERS["crawler"],
        log_dir / "crawler" / "crawler.log",
        level, formatter, max_bytes, backup_count
    )

    _add_file_handler(
        LOGGERS["crawler.rate_limiting"],
        log_dir / "crawler" / "rate_limiting.log",
        level, formatter, max_bytes, backup_count
    )

    _add_file_handler(
        LOGGERS["crawler.extraction"],
        log_dir / "crawler" / "extraction.log",
        level, formatter, max_bytes, backup_count
    )

    # Processor logs
    _add_file_handler(
        LOGGERS["processor"],
        log_dir / "processor" / "processor.log",
        level, formatter, max_bytes, backup_count
    )

    _add_file_handler(
        LOGGERS["processor.discovery"],
        log_dir / "processor" / "character_discovery.log",
        level, formatter, max_bytes, backup_count
    )

    _add_file_handler(
        LOGGERS["processor.profiles"],
        log_dir / "processor" / "profile_building.log",
        level, formatter, max_bytes, backup_count
    )

    _add_file_handler(
        LOGGERS["processor.knowledge_builder"],
        log_dir / "processor" / "knowledge_building.log",
        level, formatter, max_bytes, backup_count
    )

    _add_file_handler(
        LOGGERS["processor.rag"],
        log_dir / "processor" / "rag.log",
        level, formatter, max_bytes, backup_count
    )

    # LLM logs
    _add_file_handler(
        LOGGERS["llm"],
        log_dir / "llm" / "llm_calls.log",
        level, formatter, max_bytes, backup_count
    )


def _add_file_handler(
    logger_name: str,
    file_path: Path,
    level: int,
    formatter: logging.Formatter,
    max_bytes: int,
    backup_count: int
):
    """Add a rotating file handler to a logger."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # Logger captures everything, handler filters

    handler = RotatingFileHandler(
        file_path,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(module: str) -> logging.Logger:
    """
    Get a module-specific logger.

    Args:
        module: Module name (e.g., "crawler", "processor", "llm")

    Returns:
        Logger instance

    Example:
        logger = get_logger("crawler")
        logger.info("Started crawling")
    """
    logger_name = LOGGERS.get(module)
    if not logger_name:
        raise ValueError(
            f"Unknown module: {module}. "
            f"Valid modules: {list(LOGGERS.keys())}"
        )
    return logging.getLogger(logger_name)


def get_llm_logger(log_dir: Optional[Path] = None) -> LLMLogger:
    """
    Get specialized LLM communication logger.

    Args:
        log_dir: Log directory (auto-detected if not provided)

    Returns:
        LLMLogger instance

    Example:
        llm_logger = get_llm_logger()
        llm_logger.log_prompt(
            prompt="Is Aang a character?",
            model="claude-sonnet-4",
            purpose="character_classification",
            response="Yes",
            usage={"input_tokens": 100, "output_tokens": 20},
            cost=0.0015
        )
    """
    if log_dir is None:
        # Try to detect from existing loggers
        for handler in logging.getLogger().handlers:
            if isinstance(handler, RotatingFileHandler):
                log_dir = Path(handler.baseFilename).parent
                break

        if log_dir is None:
            raise RuntimeError(
                "Could not detect log directory. "
                "Call setup_logging() first or provide log_dir explicitly."
            )

    return LLMLogger(log_dir)
