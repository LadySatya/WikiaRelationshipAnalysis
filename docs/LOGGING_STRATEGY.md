# Logging

Logs are split by module so each stage can be debugged on its own, and every LLM call and tool call is also recorded as structured JSON. Implementation: `src/utils/logging_config.py`.

## Log directory

`setup_logging()` writes to `data/projects/<project>/logs/`:

```
logs/
  main.log                     # everything (root logger)
  errors.log                   # ERROR and above, all modules
  crawler/
    crawler.log                # crawl loop
    rate_limiting.log          # delays, robots.txt
    extraction.log             # page extraction (mostly DEBUG-level)
  processor/
    processor.log              # parent of all processor loggers (receives their messages)
    knowledge_building.log     # discover: pages, windows, saves, run summary
    rag.log                    # chunking, embeddings, vector store, retrieval
  llm/
    llm_calls.log              # one summary line per LLM call; tool calls and results
    prompts.jsonl              # structured record of each LLM call (see below)
    tool_calls.jsonl           # structured record of each tool call (see below)
```

All `.log` files rotate at 10 MB with 5 backups. Two more files, `processor/character_discovery.log` and `processor/profile_building.log`, are created but always empty; their loggers belong to code that was removed.

## Using loggers

CLI commands call `setup_project_logging()` (`src/cli/utils.py`), which runs `setup_logging()` once and prints a phase banner. In other code:

```python
from src.utils.logging_config import setup_logging, get_logger, get_llm_logger

setup_logging(project_name="avatar_wiki", log_level="INFO")  # once, at startup

logger = get_logger("processor.knowledge_builder")
logger.info("Processing page")
```

`get_logger()` raises `ValueError` for a name not in `LOGGERS`. Names in use:

| Name | Used by | File |
|---|---|---|
| `main` | CLI commands, pipeline | `main.log` |
| `crawler` | `WikiaCrawler`, session, URL manager, content saver | `crawler/crawler.log` |
| `crawler.rate_limiting` | `RateLimiter`, `RobotsParser`, `BackoffHandler` | `crawler/rate_limiting.log` |
| `crawler.extraction` | `PageExtractor`, `LinkDiscoverer` | `crawler/extraction.log` |
| `processor.knowledge_builder` | `CharacterKnowledgeBuilder` | `processor/knowledge_building.log` |
| `processor.rag` | chunker, embeddings, vector store, retriever, query engine | `processor/rag.log` |
| `llm` | `LLMClient` | `llm/llm_calls.log` |

`processor`, `processor.discovery`, `processor.profiles`, `llm.prompts` and `llm.tools` are also defined but unused.

## LLM call tracking

`get_llm_logger(log_dir=None)` returns an `LLMLogger`. Without `log_dir` it finds the directory from the handlers `setup_logging()` installed, and raises `RuntimeError` if logging is not set up (`LLMClient` catches this and skips structured logging). `CharacterKnowledgeBuilder` passes `data/projects/<project>/logs` explicitly.

```python
llm_logger = get_llm_logger()
llm_logger.log_prompt(
    prompt="...", model="claude-haiku-5-5", purpose="knowledge_building:Aang [part 1/18]",
    response="...", usage={"input_tokens": 12, "output_tokens": 5400}, cost=0.0049,
    metadata={"page_url": "https://avatar.fandom.com/wiki/Aang"},
)
llm_logger.log_tool_call(tool_name="search_characters", tool_input={"query": "Aang"}, result={"matches": [], "count": 0})
```

Each call appends a line to `llm/prompts.jsonl` or `llm/tool_calls.jsonl` and writes a summary line to `llm/llm_calls.log`. Field-by-field formats are in [DATA_SCHEMAS.md](DATA_SCHEMAS.md#llm-logs).

**Caveat:** during `discover`, every LLM call is logged twice in `prompts.jsonl`: once by `LLMClient` (`purpose: "tool_based_generation"`) and once by the knowledge builder (`purpose: "knowledge_building:<title> [part i/n]"`, with page metadata). Filter on one purpose when adding up costs.

## Useful commands

```bash
LOGS=data/projects/avatar_wiki/logs

# Follow a discover run
tail -f $LOGS/processor/knowledge_building.log

# Errors only
cat $LOGS/errors.log

# Total discover cost (count each call once)
jq -s 'map(select(.purpose | startswith("knowledge_building:"))) | map(.cost_usd // 0) | add' $LOGS/llm/prompts.jsonl

# Tool usage counts
jq -r .tool_name $LOGS/llm/tool_calls.jsonl | sort | uniq -c | sort -rn

# Calls that failed
jq 'select(.error != null)' $LOGS/llm/prompts.jsonl
```

The visualizer dashboard (`python main.py visualize <project>`) can also stream these logs live in the browser.
