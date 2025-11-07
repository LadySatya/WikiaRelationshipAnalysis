# Logging Strategy

**Problem**: All logs going to the same file makes debugging difficult. Hard to find specific module logs or LLM communication.

**Solution**: Module-specific log files + structured LLM tracking for easier debugging.

---

## 📁 Log Directory Structure

```
data/projects/<project_name>/logs/
├── main.log                    # Overall application log (everything)
├── errors.log                  # All errors across modules
├── crawler/
│   ├── crawler.log             # Crawling operations, URL management
│   ├── rate_limiting.log       # Rate limits, robots.txt, backoff
│   └── extraction.log          # Page extraction, link discovery
├── processor/
│   ├── processor.log           # General processing
│   ├── character_discovery.log # Character extraction
│   ├── profile_building.log    # Profile building
│   └── rag.log                 # RAG pipeline (chunking, embedding, retrieval)
└── llm/
    ├── llm_calls.log           # High-level LLM call summaries
    ├── prompts.jsonl           # Full prompts for debugging (structured)
    └── tool_calls.jsonl        # Tool usage tracking (structured)
```

---

## 🚀 Quick Start

### 1. Setup Logging (Once at Startup)

```python
from src.utils.logging_config import setup_logging

# In main.py or CLI command
setup_logging(
    project_name="avatar",
    log_level="INFO",          # File logs: DEBUG, INFO, WARNING, ERROR
    console_level="INFO"       # Console: INFO (less noisy)
)
```

### 2. Use Module-Specific Loggers

```python
from src.utils.logging_config import get_logger

# In crawler module
logger = get_logger("crawler")
logger.info("Started crawling https://avatar.fandom.com")
logger.warning("Rate limit hit, backing off 30s")
logger.error("Failed to fetch page", exc_info=True)

# In rate limiting module
logger = get_logger("crawler.rate_limiting")
logger.debug("robots.txt: Disallow /admin/")
logger.info("Crawl delay: 1.0s")

# In processor module
logger = get_logger("processor.discovery")
logger.info("Discovered 45 characters")
logger.debug(f"Character: Aang (confidence=0.92)")
```

### 3. Track LLM Communication

```python
from src.utils.logging_config import get_llm_logger

llm_logger = get_llm_logger()

# Log prompt/response
llm_logger.log_prompt(
    prompt="Is Aang a character? Reply yes/no.",
    model="claude-sonnet-4",
    purpose="character_classification",
    response="yes",
    usage={"input_tokens": 100, "output_tokens": 5},
    cost=0.00015
)

# Log tool calls
llm_logger.log_tool_call(
    tool_name="WikiSearchTool",
    tool_input={"query": "Aang relationships"},
    result={"found": 15, "chunks": [...]},
    execution_time_ms=245.3
)
```

---

## 📊 Log Formats

### Standard Logs (Human-Readable)

```
2025-01-06 15:30:45 | wikia.crawler                | INFO     | Started crawling https://avatar.fandom.com
2025-01-06 15:30:46 | wikia.crawler.rate_limiting  | INFO     | Crawl delay: 1.0s
2025-01-06 15:30:47 | wikia.crawler.extraction     | INFO     | Extracted page: Aang
2025-01-06 15:30:50 | wikia.processor.discovery    | INFO     | Discovered 45 characters
2025-01-06 15:31:15 | wikia.llm                    | INFO     | LLM call [character_classification] model=claude-sonnet-4 tokens=100+5 cost=$0.0002
```

### Structured Logs (Machine-Readable JSONL)

**prompts.jsonl** - Full LLM communication for debugging:
```json
{
  "timestamp": "2025-01-06T15:31:15.123456",
  "model": "claude-sonnet-4",
  "purpose": "character_classification",
  "prompt_length": 1250,
  "prompt_preview": "Is Aang a character? Look at this infobox...",
  "response_length": 3,
  "response_preview": "yes",
  "usage": {"input_tokens": 100, "output_tokens": 5},
  "cost_usd": 0.00015,
  "error": null,
  "metadata": {"page_url": "wiki/Aang"}
}
```

**tool_calls.jsonl** - Tool usage tracking:
```json
{
  "timestamp": "2025-01-06T15:31:20.123456",
  "tool_name": "WikiSearchTool",
  "input": {"query": "Aang relationships", "k": 10},
  "result_summary": "Found 15 chunks...",
  "error": null,
  "execution_time_ms": 245.3
}
```

---

## 🎯 Usage Patterns

### Module Logger Names

| Module | Logger Name | Use For |
|--------|-------------|---------|
| `"main"` | wikia.main | Top-level application flow |
| `"crawler"` | wikia.crawler | Crawling operations |
| `"crawler.rate_limiting"` | wikia.crawler.rate_limiting | Rate limits, robots.txt, backoff |
| `"crawler.extraction"` | wikia.crawler.extraction | Page extraction, link discovery |
| `"processor"` | wikia.processor | General processing |
| `"processor.discovery"` | wikia.processor.discovery | Character discovery |
| `"processor.profiles"` | wikia.processor.profiles | Profile building |
| `"processor.rag"` | wikia.processor.rag | RAG pipeline |
| `"llm"` | wikia.llm | LLM communication |

### Convenience Functions

```python
from src.utils.logging_config import log_phase_start, log_phase_end, log_progress

# Phase boundaries (with visual separators)
log_phase_start(
    "crawler",
    "Crawling Phase",
    details={"start_url": "https://...", "max_pages": 100}
)
# ... crawl pages ...
log_phase_end(
    "crawler",
    "Crawling Phase",
    summary={"pages_crawled": 95, "errors": 2, "duration_s": 180}
)

# Progress updates
for i, page in enumerate(pages):
    process_page(page)
    if i % 10 == 0:
        log_progress("processor", current=i, total=len(pages), item="pages")
```

---

## 🔍 Debugging Workflows

### 1. Find All Errors

```bash
# All errors across modules
cat data/projects/avatar/logs/errors.log

# Module-specific errors
grep ERROR data/projects/avatar/logs/crawler/crawler.log
```

### 2. Debug LLM Issues

```bash
# See all LLM calls with cost
cat data/projects/avatar/logs/llm/llm_calls.log

# Find expensive prompts
jq 'select(.cost_usd > 0.01)' data/projects/avatar/logs/llm/prompts.jsonl

# Find failed prompts
jq 'select(.error != null)' data/projects/avatar/logs/llm/prompts.jsonl

# Check tool usage
jq 'select(.tool_name == "WikiSearchTool")' data/projects/avatar/logs/llm/tool_calls.jsonl
```

### 3. Trace Character Discovery

```bash
# Follow character discovery flow
cat data/projects/avatar/logs/processor/character_discovery.log

# See all discovered characters
grep "Discovered" data/projects/avatar/logs/processor/character_discovery.log
```

### 4. Debug Rate Limiting

```bash
# Check rate limit behavior
cat data/projects/avatar/logs/crawler/rate_limiting.log

# Find backoff events
grep "backing off" data/projects/avatar/logs/crawler/rate_limiting.log
```

---

## 🛠️ Configuration

### Log Levels

**File Logs** (detailed, for post-mortem):
- `DEBUG`: Detailed internal state (robots.txt rules, chunk metadata, etc.)
- `INFO`: Progress updates, key operations (default)
- `WARNING`: Recoverable issues (rate limit hit, retrying)
- `ERROR`: Issues requiring attention (API failures)

**Console Logs** (active monitoring):
- Usually `INFO` or `WARNING` to reduce noise
- Set separately via `console_level` parameter

### Log Rotation

Logs automatically rotate when they reach 10MB:
- Keeps 5 backup files (e.g., `crawler.log.1`, `crawler.log.2`, ...)
- Prevents unbounded disk usage
- Configure via `max_bytes` and `backup_count` parameters

---

## 📝 Integration Checklist

To integrate the new logging system:

- [ ] **Phase 1: Crawler**
  - [ ] Replace logger initialization in `WikiaCrawler` with `get_logger("crawler")`
  - [ ] Add `get_logger("crawler.rate_limiting")` to `RateLimiter`, `RobotsParser`, `BackoffHandler`
  - [ ] Add `get_logger("crawler.extraction")` to `PageExtractor`, `LinkDiscoverer`

- [ ] **Phase 2: Processor**
  - [ ] Replace logger initialization in `CharacterExtractor` with `get_logger("processor.discovery")`
  - [ ] Replace logger in `ProfileBuilder` with `get_logger("processor.profiles")`
  - [ ] Add `get_logger("processor.rag")` to `ContentChunker`, `VectorStore`, `RAGRetriever`

- [ ] **Phase 3: LLM Integration**
  - [ ] Add `llm_logger.log_prompt()` calls in `LLMClient.generate()`
  - [ ] Add `llm_logger.log_tool_call()` calls in tool execution
  - [ ] Track token usage and costs

- [ ] **Phase 4: CLI Commands**
  - [ ] Call `setup_logging()` at the start of each CLI command
  - [ ] Use `get_logger("main")` for top-level progress

---

## 🎓 Example: Complete Integration

```python
# main.py or CLI command
from src.utils.logging_config import setup_logging, get_logger, log_phase_start, log_phase_end

def crawl_command(project_name, start_url, max_pages):
    # Setup logging once
    setup_logging(project_name, log_level="INFO")
    logger = get_logger("main")

    logger.info(f"Starting crawl: {start_url}")

    # Phase 1: Crawl
    log_phase_start("crawler", "Web Crawling", {"max_pages": max_pages})
    crawler = WikiaCrawler(project_name, start_url)
    pages_crawled = crawler.crawl(max_pages)
    log_phase_end("crawler", "Web Crawling", {"pages": pages_crawled})

    # Phase 2: Process
    log_phase_start("processor", "Character Discovery")
    extractor = CharacterExtractor(project_name)
    characters = extractor.discover_characters()
    log_phase_end("processor", "Character Discovery", {"characters": len(characters)})

    logger.info("Crawl complete!")
```

---

## 💡 Best Practices

1. **Use appropriate log levels**:
   - `DEBUG`: Internal state, verbose details
   - `INFO`: Key operations, progress
   - `WARNING`: Recoverable issues
   - `ERROR`: Failures requiring attention

2. **Add context to log messages**:
   ```python
   # BAD
   logger.info("Processing page")

   # GOOD
   logger.info(f"Processing page: {url} ({i+1}/{total})")
   ```

3. **Log exceptions with stack traces**:
   ```python
   try:
       fetch_page(url)
   except Exception as e:
       logger.error(f"Failed to fetch {url}", exc_info=True)
   ```

4. **Use structured logging for LLM calls**:
   - Always log prompts with `purpose` and `metadata`
   - Track token usage and costs
   - This enables cost analysis and debugging

5. **Log phase boundaries**:
   - Use `log_phase_start()` / `log_phase_end()`
   - Makes it easy to see "where am I in the pipeline?"

---

## 🔧 Troubleshooting

**Problem**: Not seeing any logs
- **Solution**: Check that `setup_logging()` was called before getting loggers

**Problem**: Logs going to wrong file
- **Solution**: Use the correct module name (see table above)

**Problem**: Too much console output
- **Solution**: Set `console_level="WARNING"` to reduce noise

**Problem**: Want to debug specific module
- **Solution**: Set `log_level="DEBUG"` and check module-specific log file

**Problem**: Need to see full prompts
- **Solution**: Check `data/projects/<project>/logs/llm/prompts.jsonl`
