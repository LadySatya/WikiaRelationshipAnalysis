# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

WikiaAnalyzer webcrawls wikia sites, extracts character information, and uses LLM analysis to discover and visualize character relationships. File-based storage with project-oriented architecture.

## Data Schemas Reference

**CRITICAL**: Before working with JSON data structures, consult `docs/DATA_SCHEMAS.md` to avoid KeyError bugs.

Common mistakes:
- Tool calls use `tool` and `input` (NOT `tool_name` and `params`)
- Chunk metadata uses `url` and `title` (NOT `source_url` and `page_title`)
- Evidence entries use `source_url` and `page_title` (NOT `url` and `title`)

**See:** `docs/DATA_SCHEMAS.md` for complete schema definitions and cheat sheet.

## LLM Prompt Engineering Standards

**CRITICAL**: All LLM prompts MUST use Claude's best practices (XML tags, clear examples, explicit exclusions).

**Template:**
```python
query = f"""<task>Clear statement of what you want.</task>
<instructions>
1. Numbered steps
2. What to include AND what to exclude
</instructions>
<format>Explicit output format</format>
<examples>
GOOD: Example 1
BAD (DO NOT): Anti-example
</examples>"""
```

**Key Principles:**
- Use XML tags for structure
- Provide 3-5 good examples + 2-3 bad examples
- Be explicit about exclusions (not just inclusions)
- Sequential numbered instructions

**Resources:** [Claude Prompt Engineering](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview)
**Examples:** `src/processor/analysis/profile_builder.py:86-124`, `profile_builder.py:218-255`

## Commands

```bash
# Environment
pip install -e ".[dev,llm,viz]"

# Full Pipeline
python main.py pipeline <project> <url> [--max-pages N] [--max-characters N]

# Phase 1: Crawling
python main.py crawl <project> <url> [--max-pages N]
python main.py resume <project>

# Phase 2: Analysis
python main.py index <project>                    # Build vector DB
python main.py discover <project>                 # Find characters
python main.py build <project>                    # Build profiles

# Validation & Management
python main.py validate <project>
python main.py list
python main.py status <project>

# Testing (ALWAYS use -m unit during development!)
python -m pytest -m unit -v                       # Fast unit tests (~5s)
python -m pytest -m "not integration" -v          # Skip slow tests
python -m pytest tests/ -v                        # Full suite (~2-3 min, before commit)
python -m pytest -m unit --cov=src --cov-report=html

# Code Quality
black src/ tests/
isort src/ tests/
mypy src/
```

## Architecture

### Storage (`data/projects/<name>/`)
- `processed/` - Crawled pages (JSON: url, title, main_content, links, infobox_data)
- `characters/` - Discovered characters
- `relationships/` - Character profiles with relationships
- `cache/` - ChromaDB vector store
- `exports/` - Output files

### Phase 1: Crawler (COMPLETE ✅)
**Components:** `src/crawler/`
- `rate_limiting/` - RateLimiter, RobotsParser, BackoffHandler
- `core/` - WikiaCrawler, SessionManager, URLManager
- `extraction/` - PageExtractor, LinkDiscoverer
- `persistence/` - ContentSaver, CrawlState

**Config:** `config/crawler_config.yaml`, `config/rate_limits.yaml`

### Phase 2: RAG Processor (COMPLETE ✅)
**Components:** `src/processor/`

**RAG Pipeline:**
```
Crawled pages → ContentChunker → EmbeddingGenerator (Voyage AI)
→ VectorStore (ChromaDB) → RAGRetriever → QueryEngine
```

**Analysis:**
- `CharacterExtractor`: Page-based discovery (metadata → batch LLM → content)
  - 3-tier classification for cost efficiency
  - Duplicate name handling via URL filtering
  - Saves to `characters/<name>.json` or `characters/<name>_(<disambiguation>).json`

- `ProfileBuilder`: Tool-based relationship extraction
  - **Tool System** (`analysis/tools/`): WikiSearchTool, RelationshipVerifyTool, CharacterContextTool
  - Claude autonomously decides which tools to use
  - Evidence-backed claims with wiki citations
  - Extensible: Add tools without modifying ProfileBuilder

**Config:** `config/processor_config.yaml`

**Output Structure:**
```json
{
  "name": "Aang",
  "full_name": "Aang",
  "disambiguation": null,
  "source_url": "https://avatar.fandom.com/wiki/Aang",
  "name_variations": ["Aang", "Avatar Aang"],
  "discovered_via": ["metadata"],
  "mentions": 45,
  "confidence": 0.92
}
```

**Cost (100 pages, 50 characters):**
- Embeddings: $0.018
- Discovery: $0.028
- Profiles: $1.65
- **Total: ~$1.70**

### Phase 3: Visualization (PLANNED)
Graph analysis, community detection, interactive visualizations.

## TDD Requirements

**MANDATORY Workflow:**
1. Write tests first
2. Red → Green → Refactor
3. No untested code

**Test Organization:**
- Mirror `src/` structure in `tests/`
- Logical test classes (TestInit, TestValidation, etc.)
- Descriptive names, comprehensive coverage
- Independent, fast (<100ms), deterministic tests

**CRITICAL - Unit vs Integration:**
- **Unit tests** (`@pytest.mark.unit`): Mocked dependencies, <100ms
- **Integration tests** (`@pytest.mark.integration`): Real I/O, 2-3 min total
- **ALWAYS use `-m unit` during development** (integration tests are slow!)
- Separate files: `test_foo.py` (unit) vs `test_foo_integration.py` (integration)

**Test Failure Protocol:**
1. STOP and investigate (never increase timeouts blindly)
2. Diagnose root cause (infinite loop? wrong logic? bad test?)
3. Fix root cause (not symptoms)
4. Add regression tests

**Coverage Status:**
- Phase 1 Crawler: 383 tests, 73-97% coverage ✅
- Phase 2 Processor: 40+ tests per component ✅

## LLM Mocking (Cost Control)

**All tests use mocked LLM by default** (via `tests/conftest.py`):
- No API calls unless explicitly opted-in
- Mock responses from `tests/fixtures/llm_responses/`
- Tracks estimated costs for budgeting

**Fixture Format:**
```json
{
  "query": "List all major characters...",
  "pattern": "list all major characters",
  "response": "Korra\nAang\nMako\n...",
  "usage": {"input_tokens": 250, "output_tokens": 65},
  "metadata": {"purpose": "Character discovery", "notes": "..."}
}
```

**Running Tests:**
```bash
pytest -m unit                  # Mocked (free, fast)
pytest -m integration           # Mocked but slower
# Real API testing not yet implemented
```

**Maintenance:**
- Update fixtures when prompts change
- Add edge cases as discovered
- Keep responses realistic

## Windows Compatibility

**CRITICAL: NEVER use Unicode in .py files** (Windows console can't display it):
- ❌ BANNED: ≥ ≤ → ← ✓ ✗ 🔍 ✅
- ✅ USE: `>=` `<=` `->` `<-` `[OK]` `[ERROR]`

**Allowed:**
- JSON/Markdown files (UTF-8)
- Test fixtures
- **NOT .py source code**

## Logging Strategy

**Problem**: All logs in one file makes debugging difficult.
**Solution**: Module-specific logs + structured LLM tracking.

**Log Directory:**
```
data/projects/<project>/logs/
├── main.log                    # Overall application
├── errors.log                  # All errors
├── crawler/                    # Crawling logs
│   ├── crawler.log
│   ├── rate_limiting.log
│   └── extraction.log
├── processor/                  # Processing logs
│   ├── processor.log
│   ├── character_discovery.log
│   ├── profile_building.log
│   └── rag.log
└── llm/                        # LLM tracking
    ├── llm_calls.log           # Summaries
    ├── prompts.jsonl           # Full prompts (structured)
    └── tool_calls.jsonl        # Tool usage (structured)
```

**Usage:**
```python
from src.utils.logging_config import setup_logging, get_logger, get_llm_logger

# Setup once at startup
setup_logging(project_name="avatar", log_level="INFO")

# Get module-specific logger
logger = get_logger("crawler")
logger.info("Started crawling")

# Track LLM calls
llm_logger = get_llm_logger()
llm_logger.log_prompt(
    prompt="Is Aang a character?",
    model="claude-sonnet-4",
    purpose="character_classification",
    response="Yes",
    usage={"input_tokens": 100, "output_tokens": 5},
    cost=0.00015
)
```

**Module Names:**
- `"main"` - Top-level application
- `"crawler"` - Crawling operations
- `"crawler.rate_limiting"` - Rate limits, robots.txt
- `"crawler.extraction"` - Page extraction
- `"processor"` - General processing
- `"processor.discovery"` - Character discovery
- `"processor.profiles"` - Profile building
- `"processor.rag"` - RAG pipeline
- `"llm"` - LLM communication

**See:** `docs/LOGGING_STRATEGY.md` for full documentation.

## Dependencies

```bash
pip install -e ".[dev]"        # Development
pip install -e ".[dev,llm]"    # + LLM features
pip install -e ".[all]"        # Everything
```

**Extras:** `dev` (pytest, black, mypy), `llm` (anthropic, voyageai, chromadb), `viz` (plotly, networkx), `api` (fastapi)

## Development Notes

- Respect rate limits and robots.txt (ethical requirement)
- Project isolation in `data/projects/<name>/`
- Async/await throughout for efficient I/O
- Test fixtures use Avatar/Naruto characters
- Config hierarchy: global → project-specific overrides
