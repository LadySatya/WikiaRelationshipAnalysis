# Logging Migration Guide

Quick reference for migrating existing code to the new logging system.

---

## 🔄 Find and Replace Patterns

### Pattern 1: Logger Initialization

**OLD:**
```python
import logging

logger = logging.getLogger(__name__)
```

**NEW:**
```python
from src.utils.logging_config import get_logger

logger = get_logger("crawler")  # Use appropriate module name
```

### Pattern 2: Setup at Startup

**OLD:**
```python
from src.utils.logging_config import setup_project_logger

logger, log_file = setup_project_logger(project_name)
```

**NEW:**
```python
from src.utils.logging_config import setup_logging, get_logger

setup_logging(project_name, log_level="INFO")
logger = get_logger("main")
```

---

## 📋 Module-by-Module Migration

### Crawler Core (`src/crawler/core/`)

**File: `crawler.py`**
```python
# Change this:
logger = logging.getLogger(__name__)

# To this:
from src.utils.logging_config import get_logger
logger = get_logger("crawler")
```

**File: `url_manager.py`, `session_manager.py`**
```python
from src.utils.logging_config import get_logger
logger = get_logger("crawler")
```

### Crawler Rate Limiting (`src/crawler/rate_limiting/`)

**Files: `rate_limiter.py`, `robots_parser.py`, `backoff_handler.py`**
```python
# Change this:
logger = logging.getLogger(__name__)

# To this:
from src.utils.logging_config import get_logger
logger = get_logger("crawler.rate_limiting")
```

### Crawler Extraction (`src/crawler/extraction/`)

**Files: `page_extractor.py`, `link_discoverer.py`**
```python
from src.utils.logging_config import get_logger
logger = get_logger("crawler.extraction")
```

### Processor Analysis (`src/processor/analysis/`)

**File: `character_extractor.py`**
```python
from src.utils.logging_config import get_logger
logger = get_logger("processor.discovery")
```

**File: `profile_builder.py`**
```python
from src.utils.logging_config import get_logger
logger = get_logger("processor.profiles")
```

### Processor RAG (`src/processor/rag/`, `src/processor/core/`)

**Files: `vector_store.py`, `embeddings.py`, `retriever.py`, `content_chunker.py`**
```python
from src.utils.logging_config import get_logger
logger = get_logger("processor.rag")
```

### LLM Client (`src/processor/llm/llm_client.py`)

```python
from src.utils.logging_config import get_logger, get_llm_logger

logger = get_logger("llm")
llm_logger = None  # Lazy-initialized

class LLMClient:
    def __init__(self, ...):
        self.logger = logger
        self.llm_logger = None

    def _ensure_llm_logger(self):
        """Lazy-initialize LLM logger."""
        if self.llm_logger is None:
            self.llm_logger = get_llm_logger()

    async def generate(self, prompt: str, ...):
        # Log to standard logger
        self.logger.info(f"Generating LLM response for {purpose}")

        # Make API call
        response = await self.client.messages.create(...)

        # Log to LLM logger
        self._ensure_llm_logger()
        self.llm_logger.log_prompt(
            prompt=prompt,
            model=self.model,
            purpose=purpose or "general",
            response=response.content[0].text,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            },
            cost=self._calculate_cost(response.usage)
        )

        return response
```

### CLI Commands (`src/cli/`)

**All command files:**
```python
from src.utils.logging_config import setup_logging, get_logger, log_phase_start, log_phase_end

def crawl_command(args):
    # Setup logging first
    setup_logging(
        args.project,
        log_level="DEBUG" if args.verbose else "INFO"
    )

    logger = get_logger("main")
    logger.info(f"Starting crawl: {args.url}")

    # Use phase logging
    log_phase_start("crawler", "Web Crawling", {"max_pages": args.max_pages})
    # ... do work ...
    log_phase_end("crawler", "Web Crawling", {"pages_crawled": pages})
```

---

## 🧪 Testing the Migration

After migrating a module, test it:

```bash
# Run a simple crawl
python main.py crawl test-project https://avatar.fandom.com --max-pages 5

# Check logs were created
ls data/projects/test-project/logs/

# Should see:
# main.log
# errors.log
# crawler/crawler.log
# crawler/rate_limiting.log
# crawler/extraction.log
```

---

## 🎯 Priority Migration Order

1. **CLI commands** - Sets up logging for entire pipeline
2. **Crawler** - High-value debugging (rate limits, errors)
3. **LLM Client** - Cost tracking and prompt debugging
4. **Processor** - Character discovery debugging
5. **RAG Pipeline** - Chunking/embedding diagnostics

---

## 🔍 Quick Grep Commands

Find all logger initializations that need updating:

```bash
# Find old logger patterns
grep -r "logging.getLogger(__name__)" src/

# Find setup_project_logger calls
grep -r "setup_project_logger" src/

# Find print statements that should be logs
grep -r "print(" src/ --include="*.py"
```

---

## ✅ Validation Checklist

After migration, verify:

- [ ] Logs are created in `data/projects/<project>/logs/`
- [ ] Module-specific logs contain relevant messages
- [ ] `main.log` contains all logs
- [ ] `errors.log` contains only errors
- [ ] LLM logs track prompts and costs (if using LLM features)
- [ ] Console output is clean (not too noisy)
- [ ] No duplicate log messages
- [ ] Log rotation works (test with small `max_bytes`)
