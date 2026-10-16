# Development Guide

## Setup

**Dev container (recommended):** open the repo in VS Code with the Dev Containers extension. `.devcontainer/devcontainer.json` uses a Debian Python 3.12 image, creates `.venv`, and installs `.[dev,rag,viz]`. Use Debian, not Alpine: torch and chromadb publish no musl wheels.

**Manual:**

```bash
git clone https://github.com/LadySatya/WikiaRelationshipAnalysis.git
cd WikiaRelationshipAnalysis
python -m venv .venv
.venv/bin/pip install -e ".[dev,rag,viz]"
```

Extras: `dev` (pytest, black, isort, mypy, flake8), `rag` (chromadb, sentence-transformers, anthropic), `viz` (flask, networkx, plotly, ...). The `llm` extra is legacy; use `rag`.

**API key:** put `ANTHROPIC_API_KEY=...` in `.env` at the repo root (gitignored; `main.py` loads it). Only `discover` and `pipeline` call the paid API. No Voyage key is needed with the default local embeddings.

## CLI

```bash
python main.py crawl <project> <url> [--max-pages N]      # currently blocked by Fandom's Cloudflare challenge
python main.py resume <project> [--max-pages N]
python main.py index <project>                            # chunk + embed into ChromaDB (local, free)
python main.py discover <project> [--max-pages N] [--max-cost USD] [--save-frequency N]
python main.py visualize <project> [--no-open]            # http://localhost:8000/
python main.py pipeline <project> [url] [--max-pages N] [--skip-crawl]

python main.py list                                       # projects
python main.py status <project>                           # progress of each stage
python main.py view <project>                             # sample crawled content
python main.py validate <project>                         # re-verify quotes; report gaps and duplicates
```

`discover` is resumable: re-running it skips pages recorded in `cache/discovery_state.json`. To start over, delete `characters/`, `relationships/` and `cache/discovery_state.json` in the project directory.

## Testing

```bash
python -m pytest -m unit                 # 743 fast unit tests (~15 s) - use during development
python -m pytest tests/                  # + integration tests (real ChromaDB, embeddings; ~45 s)
python -m pytest -m unit --cov=src --cov-report=html
```

- Unit tests are marked `@pytest.mark.unit` and mock external dependencies; integration tests are marked `@pytest.mark.integration` and live in `*_integration.py` files.
- Coverage must stay at or above 65% (`fail_under` in `pyproject.toml`; currently ~67%). Raise the floor as coverage improves.
- Follow test-driven development: write the failing test first (see CLAUDE.md).

### LLM mocking

No test calls the real Anthropic API. `tests/conftest.py` automatically replaces `LLMClient` with `MockLLMClient` (`tests/mocks/mock_llm_client.py`) in every test, except in `test_llm_client.py` and `test_llm_tool_loop.py`, which mock the Anthropic SDK directly to test the client itself. Knowledge builder tests mock the `QueryEngine` and drive the tools directly. Canned responses in `tests/fixtures/llm_responses/` date from an older discovery design.

### Testing against the real API

There is no automated real-API test. To check a change against the live model cheaply, run `discover` on a small project with a cap, e.g. one page:

```bash
mkdir -p data/projects/measure/processed
cp data/projects/<project>/processed/<SomePage>.json data/projects/measure/processed/
python main.py index measure
python main.py discover measure --max-cost 0.20
```

## Code quality

```bash
black src/ tests/
isort src/ tests/
mypy src/
flake8 src/
```

Do not use non-ASCII characters in `.py` files (Windows consoles cannot display them): write `[OK]`, `->`, `>=`, and use `\uXXXX` escapes in strings. Unicode is fine in JSON and Markdown.

## Source layout

```
src/
  cli/          # command handlers (crawl, index, discover, pipeline, validate)
  crawler/
    core/           # WikiaCrawler, SessionManager, URLManager
    extraction/     # PageExtractor, LinkDiscoverer (not wired into the crawler)
    persistence/    # ContentSaver, CrawlState
    rate_limiting/  # RateLimiter, RobotsParser, BackoffHandler
    utils/          # URL utilities
  processor/
    config.py       # ProcessorConfig (reads config/processor_config.yaml)
    core/           # ContentChunker
    rag/            # EmbeddingGenerator, VectorStore, RAGRetriever, QueryEngine
    llm/            # LLMClient (Claude API, tool loop, caching, cost tracking)
    analysis/       # CharacterKnowledgeBuilder, kb_validation (validate/status reports)
  visualizer/
    server.py       # Flask app; graph page HTML is generated inline (vis-network)
  utils/          # logging_config, tool_schema_loader

config/
  crawler_config.yaml, rate_limits.yaml, processor_config.yaml
  llm_tools/prompts/      # discovery system prompt
  llm_tools/schemas/      # tool definitions (knowledge_building/)

tests/            # mirrors src/; fixtures/ and mocks/ for LLM mocking
data/projects/    # runtime data (gitignored)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit together and [DATA_SCHEMAS.md](DATA_SCHEMAS.md) for file formats.

## Troubleshooting

- **`No module named pip` / wrong Python in `.venv` after rebuilding the container:** the workspace (including `.venv`) survives a rebuild, so a venv created in a different image is broken. Delete it and recreate: `rm -rf .venv && python -m venv .venv && .venv/bin/pip install -e ".[dev,rag,viz]"`.
- **Crawl saves 0 pages, HTTP 403:** Fandom's Cloudflare challenge (see README). Do not try to bypass it.
- **Discover stops with "credit balance is too low":** add credits at https://console.anthropic.com/settings/billing and re-run; finished pages are skipped.
- **Discover reports a page as "partly read":** it exceeded `max_windows_per_page`; raise it in `config/processor_config.yaml` if the cost is acceptable.
- **API errors mentioning a model or `temperature`:** the code targets anthropic SDK 1.x and Claude Haiku 5.5; older models are retired and SDK 1.x has no `temperature` parameter.
