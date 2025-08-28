# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WikiaAnalyzer is a modular system that webcrawls wikia sites, extracts character information, and uses LLM analysis to discover and visualize character relationships. The project uses file-based storage with a project-oriented architecture.

## Key Development Commands

```bash
# Environment setup
pip install -e .                    # Install in development mode
pip install -e ".[dev]"             # Install with dev dependencies
pip install -e ".[dev,llm,viz]"     # Install with specific extras

# Main application interface
python main.py crawl <project_name> <wikia_url> [--max-pages N]
python main.py resume <project_name>
python main.py status <project_name>
python main.py list

# Direct crawler scripts (alternative interface)  
python scripts/crawl_wikia.py <project_name> <wikia_url> [--max-pages N] [--config path]
python scripts/resume_crawl.py <project_name> [--status] [--list]

# Testing and Quality
python -m pytest tests/test_crawler/                        # Run all crawler tests
python -m pytest tests/test_crawler/core/                   # Core crawler tests
python -m pytest tests/test_crawler/rate_limiting/          # Rate limiting tests
python -m pytest tests/test_crawler/core/test_crawl_wikia.py  # Specific test file
python -m pytest --cov=src --cov-report=html               # Test with coverage
black src/ tests/                                       # Code formatting
isort src/ tests/                                       # Import sorting
mypy src/                                              # Type checking
flake8 src/                                            # Linting
```

## Architecture & Data Flow

### Project-Based Storage Architecture
- Each wikia analysis is an isolated "project" in `data/projects/<project_name>/`
- Projects contain: `raw/`, `processed/`, `relationships/`, `cache/`, `exports/`
- Crawl state is persisted per-project for resumable crawls
- Configuration is hierarchical: global configs → project-specific overrides

### Critical Crawler Components (Phase 1 - Currently Implemented)

**Rate Limiting System** (`src/crawler/rate_limiting/`)
- `RateLimiter`: Per-domain request throttling and burst protection
- `RobotsParser`: Robots.txt compliance with caching and TTL
- `BackoffHandler`: Exponential backoff for 429/503/502 responses
- **Priority**: Rate limiting MUST be implemented first for ethical crawling

**Content Pipeline** (`src/crawler/`)
- `WikiaCrawler`: Main orchestrator, handles session management
- `PageExtractor`: BeautifulSoup-based HTML parsing 
- `WikiaParser`: Wikia/Fandom-specific content filtering and namespace handling
- `LinkDiscoverer`: Intelligent character/location page discovery
- `ContentSaver`: File-based storage with URL-to-filename mapping

**State Management**
- `CrawlState`: Session persistence and checkpoint system
- `URLManager`: Queue management with deduplication and priority
- Auto-resume capability for interrupted crawls

### Configuration System
- `config/crawler_config.yaml`: Main crawler settings (delays, namespaces, exclusions)
- `config/rate_limits.yaml`: Domain-specific rate limiting overrides
- YAML-based configuration with environment variable support

### File Organization Patterns
- All methods are currently stubbed with docstrings but not implemented
- URL normalization and filename generation handles special characters
- Content filtering removes wikia navigation/ads but preserves main content
- Test fixtures use Naruto characters as sample data

## Future Architecture (Phases 2-5)

The system is designed for 6 modular components:
1. **Crawler** (Phase 1 - current)
2. **Processor** (Phase 2 - text cleaning, character detection)
3. **Analyzer** (Phase 3 - LLM relationship extraction)
4. **Mapper** (Phase 4 - relationship graph building)
5. **Visualizer** (Phase 5 - network graphs, exports)
6. **Storage** (implemented as file-based system)

Each module will be independently testable and configurable.

## Development Notes

- All crawling must respect rate limits and robots.txt (ethical requirement)
- File-based storage chosen over database for simplicity and transparency
- Project isolation allows multiple concurrent wikia analyses
- Async/await pattern used throughout for efficient I/O
- BeautifulSoup + requests/aiohttp for web scraping
- Test fixtures and sample data use Naruto universe characters

## Dependency Management

The project uses modern Python packaging with `pyproject.toml`:

- **Core dependencies**: Web crawling essentials (aiohttp, beautifulsoup4, pyyaml)
- **Optional extras**: 
  - `dev`: Testing and code quality tools (pytest, black, mypy)
  - `llm`: LLM integration (openai, anthropic) - for future phases
  - `viz`: Visualization libraries (plotly, networkx) - for future phases
  - `api`: Web API framework (fastapi) - for future phases

**Installation patterns**:
```bash
pip install -e ".[dev]"        # Development work
pip install -e ".[dev,llm]"    # When implementing LLM features
pip install -e ".[all]"        # Full installation
```

Development tools are pre-configured: black (formatting), mypy (typing), pytest (testing), coverage (test coverage).