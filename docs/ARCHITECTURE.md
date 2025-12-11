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

The knowledge builder uses an 8-tool system where Claude autonomously decides which tools to call:
1. `search_characters` - Find existing characters by name
2. `create_character` - Add a new character to the knowledge base
3. `update_character` - Update character details
4. `get_character` - Retrieve full character profile
5. `create_relationship` - Create a new relationship between characters
6. `add_relationship_claim` - Add evidence to an existing relationship
7. `get_relationship` - Retrieve relationship details
8. `search_wiki` - Query the RAG system for additional context

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
