# Development Guide

## Setup

```bash
# Clone and install
git clone https://github.com/LadySatya/WikiaRelationshipAnalysis.git
cd WikiaRelationshipAnalysis
pip install -e ".[dev,llm,viz]"

# Set API keys
export ANTHROPIC_API_KEY="your-key"
export VOYAGE_API_KEY="your-key"
```

## Testing

```bash
# Fast unit tests (use during development)
python -m pytest -m unit -v

# Full test suite (before committing)
python -m pytest tests/ -v

# Specific components
python -m pytest tests/test_crawler/ -v
python -m pytest tests/test_processor/ -v
python -m pytest tests/test_visualizer/ -v

# With coverage
python -m pytest -m unit --cov=src --cov-report=html
```

### Test Organization

- Unit tests are marked with `@pytest.mark.unit` (fast, mocked dependencies)
- Integration tests are marked with `@pytest.mark.integration` (slower, real I/O)
- Always use `-m unit` during development for fast feedback

### LLM Mocking

All tests use mocked LLM responses by default (no API calls). Mock responses are in `tests/fixtures/llm_responses/`.

## Code Quality

```bash
# Format
black src/ tests/
isort src/ tests/

# Type check
mypy src/

# Lint
flake8 src/
```

## CLI Commands

```bash
# Full pipeline
python main.py pipeline <project> <url> [--max-pages N]

# Individual steps
python main.py crawl <project> <url> [--max-pages N]
python main.py resume <project>
python main.py index <project>
python main.py discover <project>

# Management
python main.py list
python main.py status <project>
python main.py validate <project>
```

## Project Structure

```
src/
  crawler/
    core/           # WikiaCrawler, SessionManager, URLManager
    extraction/     # PageExtractor, LinkDiscoverer
    persistence/    # ContentSaver, CrawlState
    rate_limiting/  # RateLimiter, RobotsParser, BackoffHandler
    utils/          # ContentFilter, URL utilities
  processor/
    rag/            # ContentChunker, EmbeddingGenerator, VectorStore, RAGRetriever
    analysis/       # CharacterKnowledgeBuilder
  visualizer/
    server.py       # Flask app
    viewer.html     # D3.js frontend
  cli/              # Command handlers
  utils/            # Logging, config utilities

tests/
  test_crawler/     # Mirrors src/crawler structure
  test_processor/   # Mirrors src/processor structure
  test_visualizer/  # Server and graph tests
  fixtures/         # Test data and mock responses

config/
  crawler_config.yaml
  processor_config.yaml
  rate_limits.yaml

data/projects/      # Runtime data (gitignored)
```

## Windows Compatibility

Avoid Unicode characters in Python source files (Windows console issues):
- Use `[OK]`, `[ERROR]` instead of checkmarks/crosses
- Use `>=`, `<=` instead of mathematical symbols
- Unicode is fine in JSON/Markdown files

## Troubleshooting

### Tests timing out
```bash
# Run smaller subset
python -m pytest tests/test_crawler/utils/ -v
```

### Import errors
```bash
# Reinstall in dev mode
pip install -e ".[dev]" --force-reinstall
```

### API credit issues
Discovery stops if Anthropic credits are exhausted. Check https://console.anthropic.com/settings/billing

Discovery can be resumed - it tracks processed pages and skips them on restart.
