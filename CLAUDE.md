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
- **Phase 1 (Crawler) is FULLY IMPLEMENTED and working**
- URL normalization and filename generation handles special characters
- Content filtering removes wikia navigation/ads but preserves main content
- Test fixtures use Naruto and Avatar characters as sample data
- Output files contain: url, title, main_content, links, infobox_data, namespace, related_articles

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

## Test-Driven Development (TDD) Requirements

**CRITICAL**: This project follows strict Test-Driven Development practices. All new code MUST be developed using TDD methodology.

### TDD Workflow (MANDATORY)
1. **Write Tests First**: Before implementing any functionality, write comprehensive unit tests that define the expected behavior
2. **Red Phase**: Run tests to confirm they fail (since implementation doesn't exist yet)
3. **Green Phase**: Write minimal implementation to make tests pass
4. **Refactor Phase**: Improve code quality while keeping tests green
5. **Repeat**: Continue this cycle for all new features

### Test Organization Standards
- **Mirror Source Structure**: Test directories must mirror `src/` structure exactly
- **Logical Test Classes**: Group related tests into classes (e.g., `TestComponentInit`, `TestComponentValidation`)
- **Descriptive Names**: Test methods must clearly indicate what they test
- **Comprehensive Coverage**: Include happy path, edge cases, error conditions, and boundary testing
- **Fixture Usage**: Use pytest fixtures for setup/teardown and test data

### Test Quality Requirements
- **Readable**: Tests serve as executable documentation - they must be easily understood
- **Independent**: Each test must run independently without dependencies on other tests
- **Fast**: Unit tests should execute quickly (< 100ms each typically)
- **Deterministic**: Tests must produce consistent results across runs
- **Focused**: Each test should verify one specific behavior or condition

### Current Test Coverage Status
✅ **Phase 1 - Crawler (FULLY COMPLETE)**:
- All core crawler components implemented and tested (383 passing tests)
- `src/crawler/rate_limiting/` - Rate limiter, robots parser, backoff handler (97% coverage)
- `src/crawler/core/` - Crawler, session manager, URL manager (65% coverage)
- `src/crawler/extraction/` - Page extractor, wikia parser, link discoverer
- `src/crawler/persistence/` - Content saver, crawl state (85% coverage)
- `src/crawler/utils/` - URL utils, content filters (73% coverage)
- **End-to-end tested**: Successfully crawls real wikia sites with rate limiting

🔄 **Implementation Pattern Established**:
- Comprehensive test suites with 5-8 test classes per component
- Error handling and validation tests
- Async/await testing patterns for I/O operations
- Mock usage for external dependencies
- Parameterized tests for multiple scenarios

### TDD Enforcement
- **Before Any Coding**: Always write tests first, even for small changes
- **No Untested Code**: Implementation without corresponding tests is prohibited
- **Test Maintenance**: Update tests when requirements change, before updating implementation
- **Code Reviews**: All PRs must include tests and demonstrate TDD was followed

### Testing Commands (Required Before Commits)

**CRITICAL - DO NOT RUN INTEGRATION TESTS DURING DEVELOPMENT**:
- ALWAYS use `-m "not integration"` or `-m unit` during development
- Integration tests include real sleeps/timing and take 2+ minutes
- Only run full test suite (`pytest tests/`) before commits or in CI/CD

```bash
# CORRECT: Fast unit tests only (use during development)
python -m pytest tests/test_crawler/persistence/test_crawl_state.py -m unit -v
python -m pytest -m unit -v
python -m pytest -m "not integration" -v

# WRONG: This will timeout with integration tests
python -m pytest tests/test_crawler/rate_limiting/ -v  # Contains integration tests!
python -m pytest tests/test_crawler/core/ -v            # May contain slow tests

# Run with coverage reporting (unit tests only for speed)
python -m pytest -m unit --cov=src --cov-report=html

# Run all tests before any commit (includes integration tests - slow!)
python -m pytest tests/ -v
```

### Test Separation Strategy: Unit vs Integration Tests

**Test Categories**:
- **Unit Tests**: Fast tests with mocked dependencies (<100ms each, ~140 tests)
- **Integration Tests**: Tests with real I/O or timing operations (2-3 mins total, ~20 tests)

**Pytest Markers** (configured in `pyproject.toml`):
- `@pytest.mark.unit` - Fast unit tests with mocked dependencies (run always)
- `@pytest.mark.integration` - Integration tests with real I/O or timing (run on PR/nightly)
- `@pytest.mark.slow` - Tests that take >1 second (run less frequently)
- `@pytest.mark.timing` - Tests that verify actual timing behavior
- `@pytest.mark.network` - Tests that require network access (skip in offline mode)

**Running Tests by Category**:
```bash
# Fast unit tests only (development workflow - ~5 seconds)
python -m pytest -m unit -v

# Integration tests only (pre-commit verification - ~2-3 minutes)
python -m pytest -m integration -v

# All unit tests except slow/integration (quick verification)
python -m pytest -m "not integration and not slow" -v

# All tests including integration (full test suite - CI/CD)
python -m pytest tests/ -v

# Skip network-dependent tests (offline development)
python -m pytest -m "not network" -v
```

**Test File Organization**:
- **Pure Unit Test Files**: Files with ONLY unit tests use `pytestmark = pytest.mark.unit` at module level
  - Example: `test_rate_limiter.py`, `test_backoff_handler.py`, `test_crawl_state.py`
- **Integration Test Files**: Separate `*_integration.py` files use `pytestmark = pytest.mark.integration`
  - Example: `test_rate_limiter_integration.py`, `test_backoff_handler_integration.py`
- **Mixed Files** (AVOID): If unavoidable, mark each test individually (no module-level `pytestmark`)

**Why Separate Files?**:
- Module-level `pytestmark` applies to ALL tests in the file
- Individual `@pytest.mark.integration` decorators ADD markers (don't override)
- Tests with BOTH markers (`unit` AND `integration`) match `-m unit` causing timeouts
- Solution: Separate integration tests into dedicated `*_integration.py` files

**Development Workflow**:
1. During active development: `pytest -m unit -v` (fast feedback loop, ~5s)
2. Before committing: `pytest -m unit --cov=src -v` (unit tests with coverage, ~10s)
3. Before pushing: `pytest tests/ -v` (full suite including integration, ~2-3 mins)
4. CI/CD pipeline: `pytest tests/ --cov=src --cov-fail-under=80` (full suite + coverage requirement)

**Remember**: Tests are not just for catching bugs - they define the contract and behavior of your code. Write them as if they are the specification document.

## Windows Compatibility Notes

**CRITICAL**: When writing log messages, status updates, or console output, avoid Unicode symbols and emojis that don't render properly on Windows terminals. Use text-based indicators instead:

- ✓ AVOID: "✓ Success", "✗ Error", "🔍 Processing"
- ✓ USE: "[OK] Success", "[ERROR] Error", "[INFO] Processing"

This ensures compatibility across Windows Command Prompt, PowerShell, and Git Bash environments.

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