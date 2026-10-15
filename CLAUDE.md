# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

WikiaAnalyzer ingests a Fandom/Wikia wiki, uses Claude to extract characters and relationships, and visualizes them. File-based storage, one directory per project.

**Goal:** draw connections from the ingested wiki text alone. Claude has likely seen popular wikis (e.g. Avatar) in training, so plausible output proves nothing. Every relationship claim must quote the page it came from, and that quote is verified in code. Judge results by grounding in the ingested text, not by whether they look right.

## Respectful Crawling (NON-NEGOTIABLE)

This is a respectful project: it must never put meaningful load on any website (no accidental DDoS - keep rate limits conservative) and it always honors the wishes of the people who run the sites (robots.txt, terms of use, official APIs where offered). There will never, under any circumstances, be an attempt to get around Cloudflare challenges, bot detection, CAPTCHAs, IP blocks, or any similar protection - no spoofed browser user agents, challenge solvers, headless-browser evasion, or proxy rotation. If a site blocks us, we use its sanctioned access route or stop.

## Data Schemas Reference

**CRITICAL**: Before working with JSON data structures, consult `docs/DATA_SCHEMAS.md` to avoid KeyError bugs.

Common mistakes:
- Knowledge base evidence uses `evidence_url` and `evidence_text` (NOT `source_url`, `page_title`, `url`)
- Chunk metadata and citation evidence use `url` and `title` (NOT `source_url` and `page_title`)
- `generate_with_tools` tool calls use `tool` and `input`; `logs/llm/tool_calls.jsonl` uses `tool_name`
- Characters have `source_urls` (a list), not `source_url`
- The in-memory KB is nested by canon: `kb["characters"][canon][name]`, `kb["relationships"][canon][(a, b)]` - iterate canons first

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
**Examples:** `config/llm_tools/prompts/knowledge_building_system.txt` (system prompt with `<evidence_quality>` GOOD/BAD examples), `config/llm_tools/schemas/knowledge_building/add_relationship.json` (tool description)

## Commands

```bash
# Environment (the dev container does this automatically)
python -m venv .venv && .venv/bin/pip install -e ".[dev,rag,viz]"
# ANTHROPIC_API_KEY goes in .env (loaded by main.py)

# Pipeline
python main.py crawl <project> <url> [--max-pages N]   # BLOCKED: Fandom Cloudflare challenge (see below)
python main.py resume <project>
python main.py index <project>                          # Build vector DB (local embeddings, free)
python main.py discover <project> [--max-pages N] [--max-cost USD]  # Build knowledge base (resumable, paid API)
python main.py visualize <project> [--no-open]          # http://localhost:8000/
python main.py pipeline <project> [url] [--skip-crawl]

# Management
python main.py list
python main.py status <project>     # known issue: misreports indexing
python main.py view <project>
python main.py validate <project>   # known issue: looks for obsolete graph.json

# Testing (ALWAYS use -m unit during development!)
python -m pytest -m unit -v                       # Fast unit tests (~15s)
python -m pytest tests/ -v                        # + integration tests (~45s, before commit)
python -m pytest -m unit --cov=src --cov-report=html

# Code Quality
black src/ tests/
isort src/ tests/
mypy src/
```

## Architecture

Full description: `docs/ARCHITECTURE.md`.

### Storage (`data/projects/<name>/`)
- `processed/` - Crawled pages (JSON: url, title, main_content, links, infobox_data)
- `chroma.sqlite3` (+ UUID dir) - ChromaDB vector store
- `characters/` - `<name>_<canon>.json`
- `relationships/` - `<char_a>_<char_b>_<canon>.json`
- `cache/` - crawl state, robots.txt cache, `discovery_state.json` (discover resume + partly read pages)
- `logs/` - see Logging below

### Phase 1: Crawler (`src/crawler/`) - BLOCKED
- `core/` - WikiaCrawler, SessionManager, URLManager
- `rate_limiting/` - RateLimiter, RobotsParser, BackoffHandler
- `extraction/` - PageExtractor, LinkDiscoverer (LinkDiscoverer is not wired into the crawler)
- `persistence/` - ContentSaver, CrawlState

Since October 2026 Fandom serves a Cloudflare challenge to non-browser requests, so `crawl` saves 0 pages. The MediaWiki API (`https://<wiki>.fandom.com/api.php`) still works and is the sanctioned route; never try to bypass the challenge.

**Config:** `config/crawler_config.yaml`, `config/rate_limits.yaml`

### Phase 2: Indexing + Knowledge Building (`src/processor/`)

**Indexing:**
```
processed pages -> ContentChunker -> EmbeddingGenerator (local sentence-transformers by default)
-> VectorStore (ChromaDB) -> RAGRetriever -> QueryEngine
```

**Knowledge building:** `CharacterKnowledgeBuilder` (`analysis/knowledge_builder.py`)
- **Processes pages one at a time, in windows**: each page's full text is split at sentence boundaries into windows of `window_chars` (default 6000); each window is its own short tool conversation. The knowledge base carries results between windows. Pages over `max_windows_per_page` (default 25) are logged and recorded under `partial_pages` in `cache/discovery_state.json` - never silently cut. Settings: `processor.knowledge_building` in `config/processor_config.yaml`
- **9-Tool System**: determine_canon, search_characters, create_character (create-or-get), update_character, get_character, add_relationship, get_relationship, add_affiliation, search_wiki
- **Contextual Responses**: Tools return updated state (e.g., add_relationship returns the relationship's type, summary and all claim texts) so the model avoids duplicates
- **In-Memory Knowledge Base**: Maintains characters and relationships with periodic saves; resumable
- **Prompt-Driven Workflow**: LLM guided by strong prompts; the one hard check is evidence (below)
- **Verified evidence**: add_relationship creates a relationship together with its first claim (or adds a claim to an existing one), so no relationship exists without evidence. It rejects evidence_text that is not an exact quote (ignoring case/whitespace) from the cited crawled page or its infobox; the model retries
- **Fuzzy Matching**: SequenceMatcher for character name deduplication (threshold 0.6)
- **Cost controls**: prompt caching in the tool loop (`llm_prompt_caching`), `--max-cost` spending cap (resumable)

**LLM client:** `llm/llm_client.py` - default model `claude-haiku-5-5`, `effort: medium`; anthropic SDK 1.x (no `temperature`); handles `refusal` and `max_tokens` stops; responses can start with thinking blocks, so read content by block type.

**Config:** `config/processor_config.yaml`; prompt and tool definitions in `config/llm_tools/` (only `schemas/knowledge_building/` is loaded)

### Phase 3: Visualization (`src/visualizer/server.py`)
Flask dashboard plus an interactive vis-network graph (HTML generated inline in `server.py`; `viewer.html` is unused). Slow and crowded above ~200 characters.

### Known code issues
- Every discover LLM call is logged twice in `logs/llm/prompts.jsonl` (sum costs over `knowledge_building:` entries only)
- `search_wiki` results have empty `page_title` (`knowledge_builder.py` reads `page_title`; citation evidence has `title`)
- `validate` and `status` read an obsolete `graph.json`; `status` misreports indexing
- Discover page order is filesystem order, so results are not fully reproducible

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
- **Integration tests** (`@pytest.mark.integration`): Real I/O
- **ALWAYS use `-m unit` during development**
- Separate files: `test_foo.py` (unit) vs `test_foo_integration.py` (integration)

**Test Failure Protocol:**
1. STOP and investigate (never increase timeouts blindly)
2. Diagnose root cause (infinite loop? wrong logic? bad test?)
3. Fix root cause (not symptoms)
4. Add regression tests

**Coverage Status:** 743 unit tests, ~67% coverage. `pyproject.toml` enforces a 65% floor; raise it as coverage improves.

## Verify Real Behavior, Not Just Tests

Unit tests mock the LLM, so they cannot show what the model is actually given or whether its output is right. A silent 3000-character truncation went unnoticed for ten months this way. When changing discovery, prompts, extraction or the LLM client:
- Run `discover` on a small real project with `--max-cost` (a one-page project costs cents; see `docs/DEVELOPMENT.md`)
- Check the output itself (claims, quotes, counts) and the cost, not just that the command finished
- Never let a limit cut data silently - log it and record it
- Check docs against code when changing behavior; don't trust summaries (including commit messages) without looking

## LLM Mocking (Cost Control)

**No test calls the real API.** `tests/conftest.py` automatically replaces `LLMClient` with `MockLLMClient` (`tests/mocks/mock_llm_client.py`) in every test, except `test_llm_client.py` and `test_llm_tool_loop.py`, which mock the Anthropic SDK directly. Knowledge builder tests mock `QueryEngine` and call the tool methods directly. Canned responses in `tests/fixtures/llm_responses/` (format below) date from an older discovery design; update them if `MockLLMClient.generate` callers change.

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

## Windows Compatibility

**CRITICAL: NEVER use Unicode in .py files** (Windows console can't display it):
- ❌ BANNED: ≥ ≤ → ← ✓ ✗ 🔍 ✅
- ✅ USE: `>=` `<=` `->` `<-` `[OK]` `[ERROR]`, and `\uXXXX` escapes inside strings

**Allowed:**
- JSON/Markdown files (UTF-8)
- Test fixtures
- **NOT .py source code**

## Logging

Module-specific logs plus structured LLM tracking, in `data/projects/<project>/logs/`:

```
main.log, errors.log
crawler/      crawler.log, rate_limiting.log, extraction.log
processor/    processor.log, knowledge_building.log, rag.log
llm/          llm_calls.log, prompts.jsonl, tool_calls.jsonl
```

```python
from src.utils.logging_config import setup_logging, get_logger, get_llm_logger

setup_logging(project_name="avatar_wiki", log_level="INFO")   # once at startup (CLI: setup_project_logging)
logger = get_logger("processor.knowledge_builder")
```

**Module names in use:** `main`, `crawler`, `crawler.rate_limiting`, `crawler.extraction`, `processor.knowledge_builder`, `processor.rag`, `llm`. (`processor`, `processor.discovery`, `processor.profiles`, `llm.prompts`, `llm.tools` are defined but unused.)

**See:** `docs/LOGGING_STRATEGY.md` for details and useful `jq` commands.

## Dependencies

```bash
pip install -e ".[dev]"            # Development tools
pip install -e ".[dev,rag,viz]"    # Everything the pipeline needs
```

**Extras:** `dev` (pytest, black, isort, mypy, flake8), `rag` (chromadb, sentence-transformers, anthropic, tiktoken), `viz` (flask, networkx, plotly, ...), `api` (fastapi - unused). `llm` is a legacy extra; use `rag`.

## Development Notes

- Respect rate limits and robots.txt (ethical requirement; see Respectful Crawling)
- Project isolation in `data/projects/<name>/`
- The crawler is async; indexing and discovery are synchronous
- One config file per area in `config/`; no per-project overrides
- Test fixtures use Avatar/Naruto characters
- `docs/archive/` holds historical reports that do not describe the current code
