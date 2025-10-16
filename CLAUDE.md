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

# Resume crawling (implicit - just run crawl_wikia.py again with same project name)
# The crawler automatically loads previous queue/visited URLs from the project

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
- `CrawlState`: Session persistence and statistics tracking
- `URLManager`: Queue management with deduplication and priority
- **Implicit Resume**: URLManager automatically loads previous queue/visited URLs on init
  - To resume a crawl, simply run `crawl_wikia.py` again with the same project name
  - No explicit resume command needed - state is automatically restored
  - State is saved periodically (configurable) and on completion

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

## Phase 2: RAG-Based Character Analysis (PLANNED - Next Implementation)

Phase 2 uses a **Retrieval Augmented Generation (RAG)** approach to analyze the large corpus of crawled wiki data and extract character information and relationships.

### RAG Architecture Overview

Instead of processing every page individually, Phase 2:
1. **Indexes** all crawled content into a vector database (ChromaDB)
2. **Queries** the RAG system with natural language to discover characters
3. **Extracts** structured character profiles using LLM + retrieved context
4. **Builds** character relationship graphs from RAG responses

**Component Structure:** `src/processor/`
```
src/processor/
├── core/
│   ├── processor.py              # Main orchestrator
│   └── content_chunker.py        # Split pages into semantic chunks
├── rag/
│   ├── embeddings.py             # Generate embeddings (OpenAI/local)
│   ├── vector_store.py           # Vector database (ChromaDB)
│   ├── retriever.py              # Semantic search and retrieval
│   └── query_engine.py           # RAG query interface (retrieval + LLM)
├── analysis/
│   ├── character_extractor.py   # Discover characters from corpus
│   └── profile_builder.py       # Build character profiles using RAG
└── llm/
    ├── llm_client.py             # LLM API wrapper (OpenAI/Anthropic)
    └── prompts.py                # RAG prompt templates
```

### RAG Workflow

**Phase 2a: Indexing (one-time per project)**
```
Raw crawled pages (from Phase 1)
    ↓
Split into semantic chunks (paragraphs/sections)
    ↓
Generate embeddings using Voyage AI (voyage-3-lite)
    ↓
Store in ChromaDB vector database
    ↓
Index ready for semantic search
```

**Phase 2b: Character Discovery & Profile Building**
```
1. Query RAG: "What characters are mentioned in this wiki?"
   ↓ (RAG retrieves relevant chunks)
2. LLM extracts character names from context
   ↓
3. For each character:
   - Query RAG: "Who is [Character]? What are their relationships?"
   - Query RAG: "What are [Character]'s abilities and affiliations?"
   ↓ (RAG retrieves character-specific chunks)
4. LLM synthesizes structured character profile
   ↓
5. Save to data/projects/<name>/characters/
```

### Key Components

**ContentChunker** ✅: Splits pages into ~500 character chunks with overlap for embedding
**ProcessorConfig** ✅: Centralized YAML config loader (singleton pattern) for all processor components
**EmbeddingGenerator** ✅: Generates vector embeddings using local models (sentence-transformers) or Voyage AI
  - Supports both local (all-MiniLM-L6-v2) and cloud (voyage-3-lite) models
  - Lazy loading for efficiency
  - Dynamic dimension detection (no hardcoded magic numbers)
  - Batch processing for performance
  - Configurable via `config/processor_config.yaml`
**VectorStore** 📋: ChromaDB-based persistent vector database with metadata filtering (NEXT)
**RAGRetriever** 📋: Semantic search to find relevant chunks for queries
**QueryEngine** 📋: Combines retrieval + LLM (Claude) to answer questions about the wiki
**CharacterExtractor** 📋: Discovers all characters using multi-query RAG approach
**ProfileBuilder** 📋: Builds comprehensive character profiles via targeted RAG queries

### Output Structure

**Character Profile** (`data/projects/<name>/characters/Aang.json`):
```json
{
  "name": "Aang",
  "discovered_at": "2025-10-09T...",
  "profile": {
    "overview": "Aang is the Avatar and last surviving Air Nomad...",
    "affiliations": ["Air Nomads", "Team Avatar"],
    "abilities": ["Airbending", "Waterbending", "Earthbending", "Firebending"],
    "relationships": [
      {
        "character": "Katara",
        "relationship_type": "romantic",
        "description": "Wife and closest companion",
        "confidence": 0.95,
        "source_chunks": ["chunk_id_1", "chunk_id_2"]
      }
    ],
    "key_events": ["Discovered in iceberg", "Defeated Fire Lord Ozai"]
  },
  "metadata": {
    "queries_used": 6,
    "chunks_analyzed": 45,
    "confidence": 0.92
  }
}
```

### Configuration (`config/processor_config.yaml`)

```yaml
processor:
  rag:
    chunk_size: 500                    # characters per chunk
    chunk_overlap: 50                  # overlap between chunks
    embedding_provider: "voyage"        # voyage|local (Anthropic recommends Voyage AI)
    embedding_model: "voyage-3-lite"   # Fast and cheap embeddings
    vector_store_type: "chromadb"
    default_k: 10                      # chunks to retrieve per query
    llm_provider: "anthropic"          # Using Claude for RAG queries
    llm_model: "claude-3-5-haiku-20241022"  # Fast and cheap for RAG
  character_discovery:
    min_mentions: 3                    # min chunks mentioning character
    confidence_threshold: 0.7
```

### CLI Commands (Planned)

```bash
# Index project for RAG queries
python main.py index <project_name>

# Discover all characters in corpus
python main.py discover-characters <project_name>

# Build specific character profile
python main.py build-profile <project_name> "Aang"

# Build all character profiles
python main.py build-all-profiles <project_name>

# Query the RAG system directly
python main.py query <project_name> "Who is Katara's brother?"
```

### Cost Estimation

**Using Claude 3.5 Haiku + Voyage AI embeddings:**

**For 100 wiki pages (500 chunks):**
- Indexing (one-time):
  - Voyage AI: 500 chunks × 300 tokens = 150K tokens × $0.12/1M = **$0.018**
- Character discovery (3-5 queries):
  - Input: 5 queries × 3K tokens = 15K tokens × $1/1M = $0.015
  - Output: 5 queries × 500 tokens = 2.5K tokens × $5/1M = $0.0125
  - Total: **$0.028**
- Profile per character (6 queries):
  - Input: 6 queries × 3K tokens = 18K tokens × $1/1M = $0.018
  - Output: 6 queries × 500 tokens = 3K tokens × $5/1M = $0.015
  - Total per character: **$0.033**

**Total for 100 pages + 50 characters:**
- Embeddings: $0.018
- Discovery: $0.028
- 50 profiles: 50 × $0.033 = $1.65
- **Grand total: ~$1.70**

Still very affordable, and using Claude gives better reasoning!

### Dependencies

```bash
pip install -e ".[dev,rag]"  # Installs: anthropic, voyageai, chromadb, tiktoken, sentence-transformers
```

### Success Criteria for Phase 2

1. ✅ Successfully index 100+ pages into ChromaDB
2. ✅ RAG retrieval returns semantically relevant chunks
3. ✅ Discover 20+ characters from corpus
4. ✅ Build accurate profiles for characters (>90% accuracy)
5. ✅ Relationship extraction with source tracking
6. ✅ Total cost < $1 for full project processing
7. ✅ Ready for Phase 3 (relationship graph visualization)

### Why RAG?

- **Scalability**: Handles thousands of pages efficiently
- **Cost-Effective**: Only pays for relevant context, not full corpus
- **Accuracy**: Semantic search finds relevant information across pages
- **Source Tracking**: Know which chunks support each claim
- **Flexibility**: Can answer arbitrary questions about the wiki
- **Incremental**: Can add new pages to existing index

## Future Architecture (Phases 3-5)

The system is designed for 6 modular components:
1. **Crawler** (Phase 1 - ✅ COMPLETE)
2. **RAG Processor** (Phase 2 - 📋 PLANNED - see above)
3. **Relationship Graph Builder** (Phase 3 - character network construction)
4. **Graph Analysis** (Phase 4 - community detection, centrality measures)
5. **Visualizer** (Phase 5 - interactive network graphs, exports)
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

🔄 **Phase 2 - RAG Processor (IN PROGRESS)**:
- ✅ `src/processor/core/content_chunker.py` - Splits pages into chunks (COMPLETE)
- ✅ `src/processor/config.py` - Centralized config management (COMPLETE)
- ✅ `src/processor/rag/embeddings.py` - Generate embeddings from text (COMPLETE, 20 tests, 91% coverage)
- 📋 `src/processor/rag/vector_store.py` - ChromaDB integration (NEXT)
- 📋 `src/processor/rag/retriever.py` - Semantic search (TODO)
- 📋 `src/processor/rag/query_engine.py` - RAG query interface (TODO)
- 📋 `src/processor/llm/llm_client.py` - LLM API wrapper (TODO)

🔄 **Implementation Pattern Established**:
- Comprehensive test suites with 5-8 test classes per component
- Error handling and validation tests
- Async/await testing patterns for I/O operations
- Mock usage for external dependencies (no real model downloads or API calls)
- Parameterized tests for multiple scenarios
- Centralized config management via `src/processor/config.py`

### TDD Enforcement
- **Before Any Coding**: Always write tests first, even for small changes
- **No Untested Code**: Implementation without corresponding tests is prohibited
- **Test Maintenance**: Update tests when requirements change, before updating implementation
- **Code Reviews**: All PRs must include tests and demonstrate TDD was followed

### Test Failure Investigation Protocol (CRITICAL)

**NEVER work around test failures without understanding the root cause. Test failures are signals of bugs.**

When encountering test failures (timeouts, assertion errors, exceptions):

1. **STOP and INVESTIGATE FIRST**:
   - Read the full error message and stack trace carefully
   - Identify the exact line and condition that failed
   - Check if the failure is in test code or production code
   - Look for patterns (e.g., does it fail consistently? only certain tests?)

2. **DIAGNOSE before FIXING**:
   - If timeout: Check if it's an infinite loop, missing await, or actual performance issue
   - If assertion error: Verify the test expectation is correct AND the implementation logic
   - If exception: Trace back to the root cause, not just the symptom
   - Run the specific failing test in isolation to rule out test interdependencies

3. **PROHIBITED Shortcuts**:
   - ❌ Increasing timeout values without understanding why tests are slow
   - ❌ Commenting out failing tests "temporarily"
   - ❌ Adding try/except blocks to hide exceptions
   - ❌ Changing test assertions to match broken behavior
   - ❌ Assuming "it's just the test environment" without verification

4. **REQUIRED Actions**:
   - ✅ Reproduce the failure reliably
   - ✅ Understand the exact cause (infinite loop, wrong logic, bad test, etc.)
   - ✅ Fix the root cause in production code OR fix incorrect test expectations
   - ✅ Verify the fix resolves the issue without breaking other tests
   - ✅ Add regression tests if the bug wasn't caught by existing tests

5. **Example - Test Timeout Investigation**:
   ```bash
   # Test times out after 10 seconds
   # BAD: Increase timeout to 60 seconds
   # GOOD: Investigate why it takes >10 seconds

   # Add debug output to find where it hangs
   # Check for infinite loops (while conditions that never become false)
   # Check for missing progress in loops (start position not advancing)
   # Verify async operations are properly awaited
   # Profile the code to find the bottleneck
   ```

6. **When Tests Reveal Bugs**:
   - Tests timing out often indicate **infinite loops or missing termination conditions**
   - Tests failing intermittently often indicate **race conditions or state pollution**
   - Tests always failing indicate **incorrect implementation or incorrect test expectations**
   - **The test is usually right** - investigate implementation first

**Remember**: A test failure is a gift. It found a bug before production did. Respect it by investigating thoroughly.

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