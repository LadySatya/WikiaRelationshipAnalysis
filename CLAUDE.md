# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WikiaAnalyzer is a modular system that webcrawls wikia sites, extracts character information, and uses LLM analysis to discover and visualize character relationships. The project uses file-based storage with a project-oriented architecture.

## LLM Prompt Engineering Standards

**CRITICAL**: This project uses Claude (Anthropic) for character and relationship extraction. All LLM prompts MUST follow Claude's prompt engineering best practices to minimize errors and improve output quality.

### Required Techniques for All LLM Prompts

1. **Use XML Tags for Structure** (Highest Priority)
   ```python
   query = f"""<task>
   Clear statement of what you want Claude to do.
   </task>

   <instructions>
   Step-by-step numbered instructions.
   </instructions>

   <format>
   Explicit output format specification.
   </format>

   <examples>
   Good examples and BAD examples (what NOT to do).
   </examples>
   """
   ```

2. **Provide Clear Context**
   - Explain what the task results will be used for
   - State the intended audience for the output
   - Describe where this fits in the larger workflow

3. **Use Specific Examples (Few-Shot Prompting)**
   - Include 3-5 examples of correct output
   - Include 2-3 examples of INCORRECT output with "DO NOT DO THIS"
   - Cover edge cases in examples

4. **Be Explicit About Exclusions**
   - Don't just say what to include - say what to EXCLUDE
   - List specific patterns to avoid
   - Provide examples of invalid outputs

5. **Use Sequential Instructions**
   - Break complex tasks into numbered steps
   - Use bullet points for clarity
   - One instruction per line

### Bad vs Good Prompt Examples

**BAD** (Vague, no structure):
```python
query = f"List characters that {char_name} has relationships with."
```

**GOOD** (Structured, clear, with examples):
```python
query = f"""<task>
You are analyzing a wiki to identify character relationships.
List all OTHER CHARACTERS that {char_name} has a relationship with.
</task>

<instructions>
1. Only list NAMED INDIVIDUALS (e.g., "Katara", "Prince Zuko")
2. Do NOT list:
   - Titles or roles (e.g., "Phoenix King")
   - Groups (e.g., "Team Avatar")
   - Concepts (e.g., "friendship")
</instructions>

<format>
CHARACTER_NAME - brief_relationship_type
</format>

<examples>
Good:
1. Katara - romantic partner
2. Prince Zuko - former enemy turned ally

Bad (DO NOT DO THIS):
1. The Avatar - enemy (this is a title, not a name)
2. Team Avatar - friends (this is a group, not a person)
</examples>

Analyze the wiki content and list the characters:
"""
```

### When to Avoid Hardcoded Validation Lists

Prefer good prompt engineering over hardcoded validation:
- ✅ **Good**: Clear examples and instructions prevent bad outputs
- ❌ **Bad**: Hardcoded list of invalid keywords to filter (`["relationship type", "description", ...]`)

Hardcoded validation should only be a **last resort** for edge cases the prompt can't prevent.

### Resources

- [Claude Prompt Engineering Overview](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview)
- [Be Clear and Direct](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct)
- [Use XML Tags](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags)

**Implementation Examples:**
- `src/processor/analysis/profile_builder.py:86-124` (relationship discovery)
- `src/processor/analysis/profile_builder.py:218-255` (relationship details)

## Key Development Commands

```bash
# Environment setup
pip install -e .                    # Install in development mode
pip install -e ".[dev]"             # Install with dev dependencies
pip install -e ".[dev,llm,viz]"     # Install with specific extras

# ========== Main Application Interface (All Phases) ==========

# Full pipeline (recommended)
python main.py pipeline <project_name> <wikia_url> [--max-pages N] [--max-characters N]

# Phase 1: Crawling
python main.py crawl <project_name> <wikia_url> [--max-pages N]
python main.py resume <project_name> [--max-pages N]

# Phase 2: Processing & Analysis
python main.py index <project_name>                    # Build vector database
python main.py discover <project_name> [--min-mentions N] [--confidence THRESHOLD]
python main.py build <project_name> [--max-characters N]

# Phase 3: Validation
python main.py validate <project_name>                 # Show results and statistics

# Project Management
python main.py list                                    # List all projects
python main.py status <project_name>                   # Show project status
python main.py view <project_name>                     # View sample content

# ========== PoC Scripts (Deprecated - will be removed) ==========
# NOTE: Use main.py commands instead. These are kept temporarily for reference.
python scripts/poc_crawl_avatar.py                     # Use: python main.py crawl
python scripts/poc_index_avatar.py                     # Use: python main.py index
python scripts/poc_discover_characters.py              # Use: python main.py discover
python scripts/poc_build_relationships.py              # Use: python main.py build
python scripts/poc_validate_results.py                 # Use: python main.py validate

# ========== Testing and Quality ==========
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
- `PageExtractor`: BeautifulSoup-based HTML parsing with Fandom portable infobox extraction and namespace detection
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
- **CRITICAL: Crawler saves to `processed/` directory ONLY (not `raw/`)**
  - ContentSaver structure: `{"url": "...", "saved_at": "...", "content": {...}}`
  - Content fields: `url, title, main_content, links, infobox_data, namespace, is_disambiguation`
  - Files are saved as: `<cleaned_title>_YYYYMMDD.json` in `data/projects/<name>/processed/`
  - RAG indexing must read from `processed/` and extract the `content` field

## Phase 2: RAG-Based Character Analysis (IN PROGRESS)

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
**VectorStore** ✅: ChromaDB-based persistent vector database with metadata filtering
**RAGRetriever** ✅: Semantic search to find relevant chunks for queries
**QueryEngine** ✅: Combines retrieval + LLM (Claude) to answer questions about the wiki
**CharacterExtractor** ✅: Discovers characters using page-based classification with duplicate name handling and persistence
  - **Page-Based Discovery**: Classifies each crawled page instead of corpus-wide RAG
  - **3-Tier Classification**: Metadata (FREE) → Batch LLM (CHEAP) → Content (SELECTIVE)
  - **Duplicate Name Handling**: Parses disambiguation from titles, filters validation by source URL
  - **Persistence**: `save_characters()` saves to `data/projects/<name>/characters/` with auto-save option
  - **47 Tests**: 39 unit tests + 4 integration tests with real ChromaDB + 4 demo scenarios
**ProfileBuilder** 📋: Builds comprehensive character profiles via targeted RAG queries (NEXT)

### Output Structure

**Discovered Character** (`data/projects/<name>/characters/Aang.json`):
```json
{
  "name": "Aang",
  "full_name": "Aang",
  "disambiguation": null,
  "source_url": "https://avatar.fandom.com/wiki/Aang",
  "name_variations": ["Aang", "Avatar Aang"],
  "discovered_via": ["metadata"],
  "mentions": 45,
  "confidence": 0.92,
  "saved_at": "2025-10-22T14:30:00Z",
  "project_name": "avatar_wiki"
}
```

**Discovered Character with Disambiguation** (`data/projects/<name>/characters/Bumi_(King_of_Omashu).json`):
```json
{
  "name": "Bumi",
  "full_name": "Bumi (King of Omashu)",
  "disambiguation": "King of Omashu",
  "source_url": "https://avatar.fandom.com/wiki/Bumi_(King)",
  "name_variations": ["Bumi", "King Bumi"],
  "discovered_via": ["metadata", "title_llm"],
  "mentions": 28,
  "confidence": 0.88,
  "saved_at": "2025-10-22T14:30:00Z",
  "project_name": "avatar_wiki"
}
```

**Note**: Character profiles with relationships, abilities, etc. will be added by ProfileBuilder (Phase 2b - planned)

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

### Programmatic Usage (Available Now)

```python
from src.processor.analysis.character_extractor import CharacterExtractor

# Discover characters from crawled pages
extractor = CharacterExtractor(
    project_name="avatar_wiki",
    min_mentions=3,
    confidence_threshold=0.7
)

# Option 1: Discover and save separately
characters = extractor.discover_characters()
extractor.save_characters(characters)

# Option 2: Discover with auto-save
characters = extractor.discover_characters(save=True)

# Characters saved to: data/projects/avatar_wiki/characters/
# - Aang.json
# - Bumi_(King_of_Omashu).json
# - Bumi_(son_of_Aang).json
# ... etc
```

### CLI Commands (IMPLEMENTED ✅)

```bash
# Index project for RAG queries
python main.py index <project_name>

# Discover all characters in corpus (with auto-save)
python main.py discover <project_name> [--min-mentions N] [--confidence THRESHOLD]

# Build relationship profiles for characters
python main.py build <project_name> [--max-characters N]

# Validate and show results
python main.py validate <project_name>

# Run full pipeline
python main.py pipeline <project_name> <wikia_url> [--max-pages N] [--max-characters N]
```

**Note:** All CLI commands are now implemented and functional. See "Key Development Commands" section above for full usage details.

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

### Duplicate Character Name Handling (IMPLEMENTED ✅)

Wiki pages often have multiple characters with the same name, disambiguated by page titles (e.g., "Bumi (King of Omashu)" vs "Bumi (son of Aang)"). The system handles this using a hybrid approach:

**1. Name Parsing** (`_parse_character_name`):
- Extracts base name, disambiguation tag, and full name from page titles
- Regex pattern: `r'^(.+)\s*\((.+?)\)$'`
- Example: `"Bumi (King of Omashu)"` → base: `"Bumi"`, disambiguation: `"King of Omashu"`, full: `"Bumi (King of Omashu)"`

**2. Standardized Character Entries** (`_create_character_entry`):
```python
{
  "name": "Bumi",                           # Base name for RAG queries
  "full_name": "Bumi (King of Omashu)",     # Display name
  "disambiguation": "King of Omashu",        # Disambiguation tag
  "source_url": "wiki/Bumi_(King)",         # Unique identifier
  "name_variations": ["Bumi"],
  "discovered_via": ["metadata"]
}
```

**3. URL-Filtered Validation** (`_validate_characters`):
- Filters RAG chunks by `source_url` to prevent false merging
- Query "Bumi" returns chunks from BOTH characters → filter by URL → count separately
- Ensures each character's mentions are counted independently

**Testing**:
- 32 unit tests (including 8 duplicate name tests)
- 4 integration tests with real ChromaDB
- Comprehensive test coverage in `tests/test_processor/analysis/test_character_extractor.py`

**Cost**: Zero additional LLM calls (parsing is regex-based, filtering is local)

### Why RAG?

- **Scalability**: Handles thousands of pages efficiently
- **Cost-Effective**: Only pays for relevant context, not full corpus
- **Accuracy**: Semantic search finds relevant information across pages
- **Source Tracking**: Know which chunks support each claim
- **Flexibility**: Can answer arbitrary questions about the wiki
- **Incremental**: Can add new pages to existing index

## Architecture Status

The system is designed for modular components with a unified CLI interface:

### Implemented Components ✅
1. **Crawler** (Phase 1) - Web crawling with rate limiting, robots.txt compliance
2. **RAG Processor** (Phase 2) - Character discovery and relationship extraction
   - Content chunking and vector indexing
   - Character discovery with duplicate name handling
   - Relationship profile building with structured claims
3. **CLI Interface** (`src/cli/`) - Unified command-line interface
   - `crawl_commands.py` - Crawling and resuming
   - `processor_commands.py` - Indexing, discovery, profile building
   - `pipeline.py` - Full pipeline orchestration and validation
   - `utils.py` - Shared logging and config utilities
4. **Storage** - File-based project architecture

### Future Enhancements (Optional)
5. **Graph Analysis** - Community detection, centrality measures
6. **Visualizer** - Interactive network graphs, exports
7. **API Server** - REST API for programmatic access

Each module is independently testable and configurable.

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
- ✅ `src/processor/rag/vector_store.py` - ChromaDB integration (COMPLETE)
- ✅ `src/processor/rag/retriever.py` - Semantic search (COMPLETE)
- ✅ `src/processor/rag/query_engine.py` - RAG query interface (COMPLETE)
- ✅ `src/processor/llm/llm_client.py` - LLM API wrapper (COMPLETE)
- ✅ `src/processor/analysis/character_extractor.py` - Page-based character discovery (COMPLETE, 40 tests)
  - **32 unit tests**: Comprehensive logic testing including 8 duplicate name tests
  - **4 integration tests**: Real ChromaDB indexing, embeddings, and vector search
  - **Duplicate name handling**: Parses disambiguation, filters by URL, prevents false merging
- 📋 `src/processor/analysis/profile_builder.py` - Character profile building (NEXT)

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

### Unicode in Python Source Files

**CRITICAL**: **NEVER use Unicode characters in Python source files (.py files)**. Windows console (cmd.exe) uses CP-1252 encoding by default and cannot display most Unicode characters, causing `UnicodeEncodeError` crashes.

**BANNED Characters:**
- Mathematical symbols: ≥ ≤ ≠ ± × ÷ ∞
- Arrows: → ← ↑ ↓ ⇒ ⇔
- Checkmarks/symbols: ✓ ✗ ★ ● ■
- Greek letters: α β γ δ λ π
- Any emoji: 🔍 ✅ ❌ 🚀

**Use ASCII Alternatives:**
```python
# BAD (will crash on Windows):
logger.info(f"High (≥0.8): {count}")
logger.info("✓ Success")

# GOOD (works everywhere):
logger.info(f"High (>=0.8): {count}")
logger.info("[OK] Success")
```

**Allowed Locations for Unicode:**
- ✅ JSON data files (UTF-8 encoded)
- ✅ Markdown documentation (.md files)
- ✅ Test fixture data
- ❌ **NEVER in .py source code**

### Console Output Guidelines

When writing log messages, status updates, or console output, use text-based indicators:

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

## LLM API Mocking Strategy (CRITICAL FOR COST CONTROL)

**IMPORTANT**: Phase 2 (RAG) and beyond use LLM APIs (Anthropic Claude) which cost real money. To enable cost-free development and testing, this project implements comprehensive LLM mocking.

### Why Mock LLM APIs?

✅ **Cost Control**: Prevent accidental API spending during development
✅ **Speed**: Instant test feedback without network latency
✅ **Reliability**: Tests work offline and don't hit rate limits
✅ **Determinism**: Consistent test results across runs
✅ **Safety**: Cannot accidentally run expensive operations

### Automatic Mocking System

**All tests use mocked LLM by default** via `tests/conftest.py`:
- `LLMClient` is automatically patched with `MockLLMClient`
- No API calls are made unless explicitly opted-in
- Mock responses come from fixtures or synthetic patterns
- Token usage and costs are still tracked (for realistic estimates)

### Mock Architecture

```
tests/
├── conftest.py                    # Auto-patches LLMClient for all tests
├── mocks/
│   ├── mock_llm_client.py        # MockLLMClient implementation
│   └── __init__.py
└── fixtures/
    └── llm_responses/
        ├── character_discovery/  # Fixtures for character extraction
        │   ├── query_1_major_characters.json
        │   ├── query_2_storyline_characters.json
        │   ├── query_3_protagonists_antagonists.json
        │   ├── query_4_affiliations.json
        │   └── query_5_relationships.json
        └── __init__.py
```

### Fixture Format

Fixtures are JSON files with realistic LLM responses:

```json
{
  "query": "List all major characters mentioned in this wiki...",
  "pattern": "list all major characters",
  "response": "Korra\nAang\nMako\nBolin\nAsami Sato\n...",
  "usage": {
    "input_tokens": 250,
    "output_tokens": 65
  },
  "metadata": {
    "created_at": "2025-10-22",
    "model": "claude-3-5-haiku-20241022",
    "purpose": "Character discovery - comprehensive list",
    "notes": "Includes title variations to test deduplication"
  }
}
```

### Running Tests with Mocks

```bash
# DEFAULT: Run all tests with mocking (FREE, FAST)
pytest tests/test_processor/analysis/

# Run only unit tests (guaranteed mock)
pytest -m unit

# Run without integration tests (faster)
pytest -m "not integration"

# Show mock usage stats
pytest tests/test_processor/ -v -s  # See "mode": "MOCK" in output
```

### Using Real API (Opt-In Only)

To run tests with real Anthropic API:

```bash
# 1. Set API key
export ANTHROPIC_API_KEY="your-key-here"  # Linux/Mac
$env:ANTHROPIC_API_KEY="your-key-here"    # Windows PowerShell

# 2. Mark tests with @pytest.mark.realapi
@pytest.mark.realapi
@pytest.mark.expensive
def test_with_real_api():
    # This test will make real API calls
    pass

# 3. Run explicitly (future feature - not yet implemented)
pytest -m realapi --confirm-cost
```

**WARNING**: Real API tests are NOT YET IMPLEMENTED. All tests currently use mocks by default.

### Keeping Mocks Updated (CRITICAL MAINTENANCE)

**As you iterate on implementation and see real LLM query results, you MUST keep mock fixtures current and realistic.**

#### When to Update Mocks

1. **After implementing new LLM queries** - Record actual responses
2. **When LLM prompt changes** - Update corresponding fixture
3. **After observing unexpected real API behavior** - Add edge cases
4. **When adding new features** - Create fixtures for new query patterns

#### How to Update Mocks

**Method 1: Manual Fixture Creation** (Current)
```bash
# 1. Run component with real API once (manually with API key set)
# 2. Observe actual LLM responses
# 3. Create/update fixture file in tests/fixtures/llm_responses/
# 4. Format as JSON with metadata
```

**Method 2: Recording Mode** (Future - Not Yet Implemented)
```bash
# Will automatically record real API responses to fixtures
pytest --record-mode tests/test_processor/analysis/
```

#### Mock Quality Checklist

✅ **Realistic Responses**: Mimic actual LLM output format
✅ **Edge Cases**: Include variations, typos, title variations
✅ **Token Counts**: Estimate realistic input/output tokens
✅ **Metadata**: Document purpose, creation date, notes
✅ **Pattern Matching**: Include regex pattern for automatic matching

#### Example: Updating Character Discovery Fixtures

When you observe that real LLM returns character names with prefixes:

```json
// BEFORE (synthetic mock)
{
  "response": "Korra\nAang\nMako"
}

// AFTER (realistic based on actual API)
{
  "response": "Korra\nAvatar Aang\nFire Lord Zuko\nMaster Katara\nKorra",
  "metadata": {
    "notes": "Includes title variations (Avatar Aang, Fire Lord Zuko) and duplicates (Korra appears twice) to test deduplication logic"
  }
}
```

### Mock Response Patterns

MockLLMClient uses pattern matching to generate responses:

```python
# Built-in synthetic patterns (when no fixture matches)
SYNTHETIC_RESPONSES = {
    "character_discovery": "Korra\nAang\nMako\nBolin...",
    "protagonists": "Korra\nAang\nKatara...",
    "antagonists": "Amon\nUnalaq\nZaheer...",
    # ... more patterns
}
```

**Matching Priority**:
1. Exact fixture match (by query text)
2. Pattern-based fixture match (by regex)
3. Synthetic pattern match (built-in responses)
4. Default fallback

### Testing Guidelines with Mocks

**DO:**
- ✅ Use mocks for all unit tests
- ✅ Test logic, not LLM quality
- ✅ Verify mock mode in test output
- ✅ Update fixtures when prompts change
- ✅ Add edge cases to fixtures

**DON'T:**
- ❌ Test actual LLM response quality with mocks
- ❌ Expect mocks to handle novel queries perfectly
- ❌ Leave fixtures stale after prompt changes
- ❌ Use real API without explicit opt-in
- ❌ Commit .env files with API keys

### Mock Limitations

Mocks cannot test:
- ❌ Actual LLM response quality
- ❌ Prompt engineering effectiveness
- ❌ Real-world edge cases not in fixtures
- ❌ API rate limiting behavior
- ❌ Network error handling

**Solution**: Periodically validate with real API tests (manual, on-demand).

### Cost Tracking (Even with Mocks)

MockLLMClient tracks estimated costs as if real:

```python
# Mock usage stats look like real ones
{
    "total_input_tokens": 1250,
    "total_output_tokens": 320,
    "estimated_cost_usd": 0.0029,  # Estimated, not actual
    "mode": "MOCK"  # Indicates this is simulated
}
```

This helps:
- Estimate real costs before running live
- Optimize prompt sizes
- Track "budget" in development

### Maintenance Schedule

**Weekly** (During Active Development):
- Review mock responses for realism
- Add new fixtures for new features
- Update patterns if prompts changed

**Monthly**:
- Validate a sample of mocks against real API
- Update token estimates
- Review and clean up unused fixtures

**Before Major Releases**:
- Run real API validation suite
- Update all fixtures based on actual responses
- Document any LLM behavior changes

### Quick Reference

```bash
# Run tests with mocks (default, free)
pytest tests/test_processor/analysis/

# Check if mocks are being used
pytest -v -s  # Look for "mode": "MOCK" in output

# List all fixtures
ls tests/fixtures/llm_responses/character_discovery/

# Update a fixture
# 1. Run real API manually (set ANTHROPIC_API_KEY)
# 2. Observe response
# 3. Edit tests/fixtures/llm_responses/<category>/<fixture>.json

# Test mock coverage
# Ensure all LLM queries have corresponding fixtures or patterns
```

### Remember

**Mocks are a development tool, not a replacement for validation.**
Periodically test with real API to ensure mocks remain accurate and the system works end-to-end.