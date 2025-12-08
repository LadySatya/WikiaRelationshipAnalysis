# Wikia Character Relationship Analysis Project

## Project Overview
A modular system to webcrawl wikia sites, extract character information, and use LLM analysis to discover and visualize relationships between characters.

## Current Status

### ✅ All Phases Complete - Production-Ready System

**Phase 1 (Crawler)**, **Phase 2 (RAG Analysis)**, and **Phase 3 (Visualization)** are fully implemented and tested.

### ✅ Phase 1 Complete - Web Crawler Implementation
The core web crawling infrastructure is now fully implemented and tested:

#### **Implemented Components**
- **Rate Limiting System** - Ethical crawling with per-domain throttling and robots.txt compliance
- **Session Management** - Robust HTTP session handling with retries and backoff
- **URL Management** - Queue-based URL processing with deduplication and priority handling
- **Content Extraction** - BeautifulSoup-based HTML parsing and text extraction
- **Wikia-Specific Parsing** - Specialized content filtering for Wikia/Fandom sites
- **Link Discovery** - Intelligent relationship-aware link discovery and prioritization
- **Content Filtering** - Removal of navigation elements while preserving main content
- **Persistence Layer** - File-based storage with project organization
- **Domain Validation** - Strict filtering to ensure single-wikia scope

#### **Key Features**
- **403+ Passing Tests** - Comprehensive test coverage for all components
- **Manual Testing Interface** - Interactive test script (`test_crawler.py`) for development
- **Project-Based Storage** - Isolated data directories for each wikia analysis
- **Configuration System** - YAML-based configuration with hierarchical overrides
- **Error Handling** - Robust error handling with exponential backoff for failed requests

## System Architecture (Modular Design)

### 1. **Web Crawler Module** (`src/crawler/`) - ✅ IMPLEMENTED
- **Purpose**: Extract content from wikia sites with ethical crawling practices
- **Components**:
  - `WikiaCrawler`: Main orchestrator with session management and state persistence
  - `PageExtractor`: Extracts structured content, namespaces, and Fandom portable infoboxes
  - `LinkDiscoverer`: Relationship-aware character/location page discovery
  - `ContentFilter`: Filters wikia navigation while preserving main content
  - `SessionManager`: HTTP session handling with timeout and retry logic
  - `URLManager`: Queue management with deduplication and priority handling
  - `RateLimiter`: Per-domain request throttling with burst protection
  - `ContentSaver`: File-based storage with URL-to-filename mapping

### 2. **RAG Processor Module** (`src/processor/`) - ✅ IMPLEMENTED (Phase 2)
- **Purpose**: Index crawled data and extract character information using Retrieval Augmented Generation (RAG)
- **Approach**: Build a searchable vector database and query it intelligently with LLM-powered analysis
- **Components**:
  - **Indexing Pipeline**:
    - `ContentChunker`: Splits pages into semantic chunks (~500 chars) for embedding
    - `EmbeddingGenerator`: Generates vector embeddings (Voyage AI voyage-3-lite)
    - `VectorStore`: ChromaDB-based persistent vector database
  - **RAG Query System**:
    - `RAGRetriever`: Semantic search to find relevant chunks
    - `QueryEngine`: Combines retrieval + Claude LLM to answer questions
  - **Unified Knowledge Building**:
    - `CharacterKnowledgeBuilder`: Single-pass architecture combining discovery and relationship extraction
    - **Tool-Based Interaction**: LLM autonomously calls 8 tools (search_characters, create_character, update_character, get_character, create_relationship, add_relationship_claim, get_relationship, search_wiki)
    - **Contextual Responses**: Tools return updated state to prevent duplicate evidence
    - **In-Memory Knowledge Base**: Maintains characters and relationships with periodic saves

**Why RAG?**
- **Scalable**: Handles thousands of pages efficiently
- **Cost-Effective**: Only pays for relevant context (~$1.70 for 100 pages + 50 characters)
- **Accurate**: Semantic search finds relevant information across entire corpus
- **Source Tracking**: Know which chunks support each extracted fact
- **Flexible**: Can answer arbitrary questions about the wiki
- **Better Reasoning**: Claude 3.5 Haiku provides superior analysis quality

**Working CLI**:
```bash
python main.py index <project_name>                    # Index crawled data
python main.py discover <project_name>                 # Build knowledge base (unified character discovery + relationships)
```

### 3. **Visualization Module** (`src/visualizer/`) - ✅ IMPLEMENTED (Phase 3)
- **Purpose**: Interactive web-based visualization of character relationship networks
- **Components**:
  - `server.py`: Flask web server with SSE log streaming
  - `visualizer.py`: Graph generation and data preparation
  - `viewer.html`: D3.js force-directed graph visualization
- **Features**:
  - **Interactive Graph**: Drag nodes, zoom, pan
  - **Visual Encoding**: Node size by relationship count, edge thickness by confidence
  - **Evidence Viewer**: Click relationships to view supporting citations
  - **Live Monitoring**: Real-time log streaming during profile building
  - **Project Browser**: View all projects with status cards

**Access the Dashboard**:
```bash
python src/visualizer/server.py 8000
# Visit: http://localhost:8000/
```

### 4. **Data Storage Module** (`src/crawler/persistence/`) - ✅ IMPLEMENTED
- **Purpose**: Persist and manage data with project-based isolation
- **Components**:
  - `ContentSaver`: File-based storage with project organization
  - `CrawlState`: Session persistence for resumable crawls
- **Storage Structure**:
  - `data/projects/<name>/processed/` - Crawled pages (JSON)
  - `data/projects/<name>/characters/` - Discovered characters
  - `data/projects/<name>/relationships/` - Character profiles + graph.json
  - `data/projects/<name>/vector_store/` - ChromaDB index
  - `data/projects/<name>/logs/` - Build logs

## Technology Stack

- **Backend**: Python 3.13+ 
- **Web Crawling**: BeautifulSoup4 + aiohttp (async HTTP)
- **Testing**: pytest with comprehensive coverage (403+ tests)
- **Data Format**: JSON for structured data, YAML for configuration
- **Storage**: File-based with project isolation
- **RAG System**: ChromaDB (vector database) + Voyage AI embeddings (Phase 2)
- **LLM Integration**: Anthropic Claude API (Claude 3.5 Haiku for RAG queries)
- **Visualization**: NetworkX + Plotly/D3.js (planned for Phase 3)
- **API**: FastAPI for web interface (planned)
- **Configuration**: YAML-based config files with hierarchical overrides

## Implementation Progress

### ✅ Phase 1: Web Crawler Foundation (COMPLETED)
1. ✅ Set up project structure and configuration system
2. ✅ Implement comprehensive web crawler with rate limiting
3. ✅ Create file-based data models and storage system
4. ✅ Build text extraction and content filtering pipeline
5. ✅ Add domain validation and single-wikia scope enforcement
6. ✅ Implement comprehensive test suite (403+ tests)
7. ✅ Create manual testing interface for development

### ✅ Phase 2: RAG-Based Character Analysis (COMPLETED)
**Goal**: Build a searchable knowledge base from crawled data and extract character profiles using RAG

#### Phase 2a: Indexing ✅
1. ✅ Install RAG dependencies (`pip install -e ".[dev,rag]"` - chromadb, anthropic, voyageai)
2. ✅ Implement `ContentChunker` - Split pages into semantic chunks with overlap
3. ✅ Implement `EmbeddingGenerator` - Generate vector embeddings (Voyage AI/local)
4. ✅ Implement `VectorStore` - ChromaDB integration with persistence
5. ✅ Test end-to-end indexing on test_resume project (5 pages)

#### Phase 2b: Knowledge Building ✅
6. ✅ Implement `RAGRetriever` - Semantic search functionality
7. ✅ Implement `QueryEngine` - RAG query interface (retrieval + Claude)
8. ✅ Implement `CharacterKnowledgeBuilder` - Unified single-pass architecture
9. ✅ Implement 8-tool system with contextual responses to prevent duplicates
10. ✅ Validate on Avatar wiki data (characters discovered with relationships)

#### Phase 2c: CLI & Documentation ✅
11. ✅ Add CLI commands (index, discover, pipeline)
12. ✅ Create `config/processor_config.yaml` with RAG settings
13. ✅ Update documentation with unified architecture workflow
14. ✅ Comprehensive unit tests (51 tests for CharacterKnowledgeBuilder, 69% coverage)

**Success Criteria** (ALL MET):
- ✅ Index pages into ChromaDB successfully
- ✅ Unified knowledge building with single-pass architecture
- ✅ Tool-based extraction with evidence tracking and duplicate prevention
- ✅ Comprehensive test coverage (688 unit tests passing)
- ✅ Ready for visualization (relationship graph generation)

### ✅ Phase 3: Visualization & Interface (COMPLETED)
1. ✅ Build graph structure from character profiles
2. ✅ Implement relationship classification and confidence scoring
3. ✅ Create interactive D3.js force-directed graph visualization
4. ✅ Build Flask web server with project browser
5. ✅ Add live log monitoring with SSE streaming
6. ✅ Create evidence viewer for relationship details

**Access**: `python src/visualizer/server.py 8000` → http://localhost:8000/

### 🔄 Phase 4: Enhancements & Polish (PLANNED)
1. ✅ Unit tests for CharacterKnowledgeBuilder (51 tests, 69% coverage)
2. Implement graph search/filter functionality
3. Add export functionality (JSON, GraphML, CSV)
4. Implement community detection algorithms
5. Add relationship type visualization (color-coded edges)
6. Performance optimization for large graphs (20+ characters)

## Project Structure
```
WikiaAnalysis/
├── src/
│   └── crawler/
│       ├── core/           # Main crawler orchestration
│       ├── extraction/     # Content parsing and link discovery  
│       ├── persistence/    # Data storage and state management
│       ├── rate_limiting/  # Ethical crawling controls
│       └── utils/          # Content filtering and utilities
├── tests/
│   └── test_crawler/      # Comprehensive test suite (403+ tests)
├── config/                # Configuration templates (planned)
├── data/                  # Project data storage
├── scripts/               # CLI interfaces
├── test_crawler.py        # Manual testing interface
├── main.py               # Main application entry point
└── pyproject.toml        # Modern Python packaging
```

## Key Features
- **✅ Ethical Crawling**: Rate limiting, robots.txt compliance, and domain validation
- **✅ Robust Architecture**: Comprehensive error handling with exponential backoff
- **✅ Project Isolation**: Separate data directories for each wikia analysis
- **✅ RAG-Powered Analysis**: ChromaDB + Claude for intelligent character discovery
- **✅ Tool-Based Extraction**: LLM autonomously calls tools to gather evidence
- **✅ Evidence Tracking**: Full citation support with source URLs and confidence scores
- **✅ Interactive Visualization**: D3.js force-directed graphs with live log monitoring
- **✅ Wikia-Specialized**: Custom parsing for Fandom/Wikia site structures
- **✅ Test-Driven**: 688+ unit tests ensuring reliability
- **✅ Unified Architecture**: Single-pass knowledge building with tool-based LLM interaction

## Getting Started

### Prerequisites
```bash
Python 3.13+
pip install -e ".[dev]"  # Install with development dependencies
```

### Live Testing Results ✅

**Wikia Content Extraction Successfully Implemented** (September 2024):

Complete end-to-end testing validated full content extraction functionality:

#### Test Results Summary:
- **✅ Configuration System**: Loaded YAML config successfully with rate limiting (1.0s delay, 60 req/min)
- **✅ Project Structure**: Created proper directory hierarchy with 14 subdirectories
- **✅ URL Validation**: Successfully validated wikia URLs and domain filtering
- **✅ Rate Limiting**: Infrastructure working (observable delays between requests)
- **✅ Error Handling**: Graceful failure handling with proper HTTP status management
- **✅ Session Management**: HTTP sessions with proper cleanup
- **✅ Content Extraction**: Real content extraction from 55+ pages with rich character data
- **✅ Meaningful Filenames**: Human-readable names like `Tenzin_20250911.json`
- **✅ Link Discovery**: 527 URLs discovered from just 2 pages

#### Current Working Commands:
```bash
# Working CLI (ready to use now)
python main.py crawl my_project https://avatar.fandom.com/wiki/Avatar_Wiki --max-pages 5
python main.py status my_project
python main.py list

# Integration testing (for development)
python test_crawl.py  # End-to-end validation test
python test_resume.py  # Resume functionality test
```

#### Actual Test Results:
- **Pages crawled**: 55+ real pages with full content
- **Content types**: Characters, articles, disambiguation pages  
- **Filenames**: `Tenzin_20250911.json`, `United_Republic_Council_20250911.json`
- **Rich data**: Full biographies, abilities, relationships, infobox data
- **Link discovery**: 527 URLs from 2 pages, 2580 URLs from 50 pages
- **Error rate**: 0% on successful extractions

### Quick Start - Ready to Use Now ✅

#### Working CLI Commands:
```bash
# Full pipeline (recommended)
python main.py pipeline my_project https://avatar.fandom.com/wiki/Aang --max-pages 100

# Step-by-step workflow
python main.py crawl my_project https://avatar.fandom.com/wiki/Aang --max-pages 100
python main.py index my_project
python main.py discover my_project  # Unified character discovery + relationships
python main.py validate my_project

# Start visualization dashboard
python src/visualizer/server.py 8000
# Visit: http://localhost:8000/

# Project management
python main.py status my_project
python main.py list

# Verify installation works
python -m pytest -m unit -v
```

### Development Workflow

#### Testing Commands:
```bash
# Run full test suite (slow - 400+ tests)
python -m pytest tests/test_crawler/ -v

# Run specific component tests (faster)
python -m pytest tests/test_crawler/rate_limiting/ -v
python -m pytest tests/test_crawler/core/ -v
python -m pytest tests/test_crawler/utils/ -v

# Single test for quick verification
python -m pytest tests/test_crawler/utils/test_url_utils.py::TestURLUtilsValidation::test_validate_malformed_url -v

# Test with coverage
python -m pytest --cov=src --cov-report=html
```

#### Code Quality Commands:
```bash
# Code formatting
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/
```

### Next Development Steps (Enhancements)

All core functionality is complete! Priority enhancements:

1. **Graph Visualization Enhancements**:
   - Add search/filter functionality to find specific characters
   - Color-code edges by relationship type (romantic, familial, adversarial)
   - Optimize layout for large graphs (20+ characters)

2. **Export Functionality**:
   - JSON, GraphML, CSV formats
   - Integration with Gephi, Cytoscape, or other graph tools

3. **Advanced Analysis**:
   - Community detection (identify character factions/groups)
   - Temporal analysis (track relationship evolution)
   - Cross-wiki comparative analysis

## Troubleshooting & Common Issues

### Windows Compatibility
- **Unicode Issues**: Log messages use `[OK]`, `[ERROR]`, `[INFO]` instead of Unicode symbols
- **Path Issues**: Project uses forward slashes; Windows handles them correctly
- **Console Encoding**: Avoid emojis/Unicode symbols in output (documented in CLAUDE.md)

### Test Suite Issues
```bash
# If pytest times out on rate limiting tests:
python -m pytest tests/test_crawler/utils/ -v  # Test smaller subset

# If coverage fails (expected with stubs):
python -m pytest tests/ --cov=src --cov-fail-under=20  # Lower threshold

# Quick verification test:
python -m pytest tests/test_crawler/utils/test_url_utils.py::TestURLUtilsValidation::test_validate_malformed_url -v
```

### Installation Issues
```bash
# If pip install fails:
pip install -e ".[dev]" --user  # Install to user directory

# If dependencies conflict:
pip install -e . --upgrade  # Install base package first
```

### Testing Issues
```bash
# If test_crawl.py shows "Pages crawled: 0" - THIS IS EXPECTED
# The content extraction pipeline is not implemented yet
# This validates the infrastructure is working correctly

# If project directories not created:
ls -la data/projects/  # Check if base directories exist
mkdir -p data/projects  # Create if needed
```

### Development Continuation

#### Priority Implementation Order (Phase 1 - Complete ✅):
1. ✅ **PageExtractor** (`src/crawler/extraction/page_extractor.py`) - Extract content, namespaces, and infoboxes
2. ✅ **CrawlState** (`src/crawler/persistence/crawl_state.py`) - Save/load crawl state
3. ✅ **Main CLI** (`main.py`, `scripts/crawl_wikia.py`) - Working command interface

#### Phase 2 Next Steps:
```bash
# Implement RAG indexing pipeline:
python main.py index <project_name>                    # Index crawled data
python main.py discover-characters <project_name>      # Find characters via RAG
python main.py build-profile <project_name> "Aang"     # Build character profile
```

## Configuration
Configuration uses YAML files with hierarchical overrides. The system respects:
- Global crawler settings (rate limits, user agent)
- Per-domain rate limiting overrides
- Project-specific configuration
- Wikia namespace and content filters

### Configuration Files:
- `config/crawler_config.yaml` - Main crawler configuration
- `config/rate_limits.yaml` - Domain-specific rate limiting
- Project directories automatically created in `data/projects/<project_name>/`

## Current Capabilities ✅ FULLY WORKING

The WikiaAnalyzer can now:
1. **Extract real content** from any Fandom/Wikia site with rich character data
2. **Save human-readable files** like `Tenzin_20250911.json` instead of cryptic hashes
3. **Complete CLI interface** with crawl, status, list, and view commands
4. **Automatic categorization** into characters, articles, disambiguation pages
5. **Intelligent link discovery** finding hundreds of related pages automatically  
6. **Ethical crawling** with rate limiting (1.0s delays) and robots.txt compliance
7. **Structured JSON output** with titles, content, links, categories, and infobox data
8. **Project-based organization** with isolated storage per wikia site

**Ready for immediate use on any wikia site!**

## Contributing
This project uses modern Python development practices:
- **Type hints** throughout the codebase
- **Comprehensive testing** with pytest
- **Code formatting** with black and isort
- **Modular architecture** for independent component development

## License
MIT License (see LICENSE file)