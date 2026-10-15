# Architecture

## Overview

WikiaAnalyzer is a four-stage pipeline. Each stage reads the previous stage's files from `data/projects/<name>/`, so stages can be run (and re-run) independently.

```
Crawl -> Index -> Discover -> Visualize
```

```
Fandom wiki
    |
    v
[Crawler]            --> processed/*.json            (one file per page)
    |
    v
[Indexer]            --> chroma.sqlite3              (ChromaDB vector index)
    |
    v
[Knowledge Builder]  --> characters/*.json, relationships/*.json
    |                    cache/discovery_state.json  (resume state)
    v
[Visualizer]         --> interactive graph at http://localhost:8000/
```

The goal is to draw connections **from the ingested wiki text alone**. Because Claude has likely seen popular wikis during training, the design does not trust plausible-looking output: every relationship claim must quote the page it came from, and that quote is checked in code.

## 1. Crawler (`src/crawler/`)

Async (aiohttp) crawler with ethical defaults.

- `core/WikiaCrawler` - main loop: takes URLs from the queue, fetches, extracts, saves, and queues every link the page contains
- `core/SessionManager` - HTTP session, user agent, timeouts
- `core/URLManager` - URL queue with deduplication
- `rate_limiting/RateLimiter`, `RobotsParser`, `BackoffHandler` - per-domain delays (2 s default for Fandom), robots.txt compliance, exponential backoff
- `extraction/PageExtractor` - extracts title, main text, links and infobox fields from HTML
- `extraction/LinkDiscoverer` - link prioritization (character/lore pages first). **Not currently used by the crawler**, which follows links in page order
- `persistence/ContentSaver` - writes `processed/*.json`
- `persistence/CrawlState` - saves the queue and visited set so `resume` can continue a crawl

**Status:** since October 2026 Fandom serves a Cloudflare bot challenge to all non-browser requests, so the crawler saves 0 pages. The wiki's MediaWiki API (`api.php`) is not challenged and is the planned replacement fetch path. The project will not try to get around the challenge (see CLAUDE.md, "Respectful Crawling").

**Extraction limits worth knowing:** page text is flattened to a single line (no paragraph breaks), infobox values lose spaces between links, page categories are not collected, and the links inside the article text are not kept with the text.

## 2. Indexing (`src/processor/core`, `src/processor/rag`)

- `core/ContentChunker` - splits each page into ~500-character chunks with 50-character overlap
- `rag/EmbeddingGenerator` - embeds chunks. Default: local `sentence-transformers` model `all-MiniLM-L6-v2` (free, runs on CPU). Optional: Voyage AI (`embedding_provider: voyage`; requires `pip install voyageai` and `VOYAGE_API_KEY`)
- `rag/VectorStore` - persistent ChromaDB collection per project, stored in `data/projects/<name>/`
- `rag/RAGRetriever`, `rag/QueryEngine` - semantic search, and question answering over retrieved chunks with Claude citations

The index is used during discovery only through the optional `search_wiki` tool (rarely called - about 5 times in a 20-page run). Discovery itself reads pages directly; see [Design notes](#design-notes).

## 3. Knowledge Building (`src/processor/analysis/knowledge_builder.py`)

`CharacterKnowledgeBuilder` (run by `python main.py discover <project>`) processes crawled pages one at a time and maintains an in-memory knowledge base that Claude edits through tools.

### Reading pages in windows

Each page's text is split at sentence boundaries into windows of at most `window_chars` characters (default 6000). Every window is its own short tool conversation; the knowledge base carries what earlier windows found, and later windows are told the page's canon and that earlier parts are already processed. The full infobox is sent with the first window.

A page with more than `max_windows_per_page` windows (default 25, about 150,000 characters) is only partly read. This is logged, recorded under `partial_pages` in `cache/discovery_state.json`, and reported in the run summary.

### Tools

In each window Claude decides which tools to call (definitions in `config/llm_tools/schemas/knowledge_building/`, system prompt in `config/llm_tools/prompts/knowledge_building_system.txt`):

1. `determine_canon` - declare the page's canon (main, film, ...)
2. `search_characters` - fuzzy name search (SequenceMatcher, threshold 0.6) to avoid duplicates
3. `create_character` - add a character; returns the existing record if the name exists
4. `update_character` - add aliases, sources, or update the bio
5. `get_character` - full character record
6. `add_relationship` - record a relationship together with one evidence-backed claim; creates the relationship if new, otherwise adds the claim
7. `get_relationship` - full relationship record with all evidence
8. `add_affiliation` - record membership in a group (teams, nations, organizations)
9. `search_wiki` - semantic search over the index for more context

Tool results show the current state (existing claims, close name matches) so the model can avoid duplicates. Errors are returned to the model, not raised.

### Verified evidence

`add_relationship` checks that `evidence_text` appears on the cited crawled page (main text or a `Key: value` infobox line), ignoring case, whitespace and typographic quotes. If it does not, nothing is stored and the model is asked to quote exactly. Because the relationship and its first claim are created in one call, no relationship exists without verified evidence. Quotes from lists (e.g. an infobox "Relatives" line) count as evidence.

### LLM client (`src/processor/llm/llm_client.py`)

- Model `claude-haiku-5-5` by default with `effort: medium` (`processor_config.yaml`)
- Tool loop (`generate_with_tools`): up to 50 rounds per window; keeps the task plus the last 10 exchanges and strips thinking blocks from kept turns when it prunes (required by the API once history changes)
- Prompt caching: the system prompt and tool definitions are cached, plus automatic caching of the growing conversation
- Cost tracking includes cache reads (0.1x input price) and writes (1.25x)
- A `refusal` or `max_tokens` stop raises a clear error rather than returning empty text

### Running, resuming, and cost

- The page order is the order of files in `processed/` (filesystem order).
- A page is marked done in `cache/discovery_state.json` only after all its windows succeed; re-running `discover` skips done pages.
- `--max-cost USD` stops starting new pages once the run has spent that much (it can overshoot by one page).
- After 5 consecutive page failures, or if API credits run out, the run saves and stops.
- Measured with Claude Haiku 5.5 and caching: about $0.08 and 6 minutes for the 102,000-character Aang page. Output tokens (thinking plus tool calls) are most of the cost.

## 4. Visualizer (`src/visualizer/server.py`)

A Flask app (`python main.py visualize <project>`, port 8000):

- `/` - dashboard listing projects, with live log streaming (Server-Sent Events)
- `/<project>` - interactive graph rendered in the browser with **vis-network** (HTML is generated inline in `server.py`). Nodes are characters; edge width reflects the number of evidence quotes (capped at 5). Click a character for their bio and relationships, or a relationship for its claims and quotes. A canon filter selects one continuity.
- JSON API under `/api/<project>/...` for relationships, characters (`characters/<name>?canon=<canon>`), and canons

The graph loads every relationship file with a separate request and lays out nodes with a physics simulation in the browser, so large projects (200+ characters) load slowly and are crowded. `src/visualizer/viewer.html` is an old D3.js viewer that is no longer served.

## Configuration

- `config/crawler_config.yaml` - user agent, delays, target namespaces
- `config/rate_limits.yaml` - per-domain rate limits
- `config/processor_config.yaml` - chunking, embeddings, LLM model, effort, prompt caching, and `knowledge_building.window_chars` / `max_windows_per_page`
- `config/llm_tools/` - discovery system prompt and tool definitions (`schemas/relationship_extraction/` and `schemas/character_classification/` are leftovers that nothing loads)

There is one config file per area; there are no per-project overrides. Secrets (`ANTHROPIC_API_KEY`) come from `.env`, loaded by `main.py`.

## Design notes

**Why read pages directly instead of RAG-first?** An earlier version of these docs described discovery as RAG-driven. In practice discovery reads each page in full and uses RAG only on request (`search_wiki`). Reading directly means every page is covered, and verified quotes tie each claim to its source page. With current model pricing and context sizes (Haiku 5.5: 1M-token context, $0.10 per million input tokens), retrieval is not the bottleneck it was when the project started.

**Known gaps and possible next steps:**
- Fetch pages via the MediaWiki API (unblocks crawling; also provides categories, clean infobox fields, and links)
- Use wiki page links to identify characters instead of fuzzy name matching ("Bumi" vs "King Bumi")
- Split discovery into a parallel "read each window" step and a deterministic "merge" step for speed and reproducibility
- A cross-wiki checking pass: for each relationship, retrieve passages from the whole index that mention both characters
- Faster, more readable visualization: one bulk request, precomputed layout, focus-on-a-character view, filters
