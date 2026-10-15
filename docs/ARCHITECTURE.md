# Architecture

## System Overview

WikiaAnalyzer is built as a modular pipeline with four main phases:

```
Crawl -> Index -> Discover -> Visualize
```

Each phase can be run independently, and operations are resumable.

## Module Structure

### 1. Web Crawler (`src/crawler/`)

Extracts content from Fandom/Wikia sites with ethical crawling practices.

**Components:**
- `core/WikiaCrawler` - Main orchestrator with session management and state persistence
- `extraction/PageExtractor` - Extracts structured content, namespaces, and portable infoboxes
- `extraction/LinkDiscoverer` - Relationship-aware character/location page discovery
- `utils/ContentFilter` - Filters wikia navigation while preserving main content
- `core/SessionManager` - HTTP session handling with timeout and retry logic
- `core/URLManager` - Queue management with deduplication and priority handling
- `rate_limiting/RateLimiter` - Per-domain request throttling with burst protection
- `persistence/ContentSaver` - File-based storage with URL-to-filename mapping
- `persistence/CrawlState` - Session persistence for resumable crawls

### 2. RAG Processor (`src/processor/`)

Indexes crawled data and extracts character information using Retrieval Augmented Generation.

**Indexing Pipeline:**
- `rag/ContentChunker` - Splits pages into semantic chunks (~500 chars) for embedding
- `rag/EmbeddingGenerator` - Generates vector embeddings via Voyage AI (voyage-3-lite)
- `rag/VectorStore` - ChromaDB-based persistent vector database

**Query System:**
- `rag/RAGRetriever` - Semantic search to find relevant chunks
- `rag/QueryEngine` - Combines retrieval + Claude LLM to answer questions

**Knowledge Building:**
- `analysis/CharacterKnowledgeBuilder` - Single-pass architecture combining discovery and relationship extraction

The knowledge builder reads each crawled page in full, one window at a time: the page text is split at sentence boundaries into windows of up to 6000 characters (`processor.knowledge_building.window_chars`), and each window is processed in its own short tool conversation. The knowledge base carries what earlier windows found. A per-page cap (`max_windows_per_page`, default 25) limits cost; pages over it are logged and recorded as partly read in `cache/discovery_state.json`.

In each window, Claude autonomously decides which of 10 tools to call:
1. `determine_canon` - Declare which canon (main, film, ...) the page belongs to
2. `search_characters` - Find existing characters by name (fuzzy match)
3. `create_character` - Add a new character to the knowledge base
4. `update_character` - Update character details
5. `get_character` - Retrieve full character profile
6. `create_relationship` - Create a new relationship between characters
7. `add_relationship_claim` - Add an evidence-backed claim to a relationship
8. `get_relationship` - Retrieve relationship details
9. `add_affiliation` - Record a character's membership in a group
10. `search_wiki` - Query the RAG system for additional context

Evidence is verified: `add_relationship_claim` rejects any `evidence_text` that is not an exact quote (ignoring case and whitespace) from the cited crawled page or its infobox, and the model retries. This keeps claims grounded in the ingested text rather than the model's prior knowledge of the wiki.

Tools return contextual responses (e.g., existing evidence) to prevent duplicates.

### 3. Visualizer (`src/visualizer/`)

Interactive web-based visualization of character relationship networks.

**Components:**
- `server.py` - Flask web server with SSE log streaming
- `visualizer.py` - Graph generation and data preparation
- `viewer.html` - D3.js force-directed graph visualization

**Features:**
- Drag nodes, zoom, pan
- Node size reflects relationship count
- Edge thickness reflects confidence
- Click relationships to view supporting citations
- Real-time log streaming during discovery
- Project browser with status cards

## Data Flow

```
Fandom Wiki
    |
    v
[Crawler] --> data/projects/<name>/processed/*.json
    |
    v
[Indexer] --> data/projects/<name>/cache/chroma.sqlite3
    |
    v
[Knowledge Builder] --> data/projects/<name>/characters/*.json
                    --> data/projects/<name>/relationships/*.json
    |
    v
[Visualizer] --> Interactive D3.js graph
```

## Why RAG?

Direct LLM analysis of thousands of wiki pages would be:
- Expensive (entire corpus in context)
- Limited (context window constraints)
- Slow (sequential processing)

RAG approach:
- **Scalable** - Handles thousands of pages efficiently
- **Cost-effective** - Only pays for relevant context (~$0.10-0.15 per page)
- **Accurate** - Semantic search finds relevant information across entire corpus
- **Traceable** - Know which chunks support each extracted fact
- **Flexible** - Can answer arbitrary questions about the wiki

## Configuration

Configuration uses YAML files with hierarchical overrides:

- `config/crawler_config.yaml` - Rate limits, user agent, timeouts
- `config/processor_config.yaml` - Chunk sizes, embedding model, LLM settings
- `config/rate_limits.yaml` - Per-domain rate limiting overrides

Project-specific data is isolated in `data/projects/<project_name>/`.
