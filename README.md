# Wikia Character Relationship Analysis Project

## Project Overview
A modular system to webcrawl wikia sites, extract character information, and use LLM analysis to discover and visualize relationships between characters.

## Current Status

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
  - `PageExtractor`: Extracts structured content from wikia pages
  - `WikiaParser`: Wikia/Fandom-specific content parsing and namespace handling
  - `LinkDiscoverer`: Relationship-aware character/location page discovery
  - `ContentFilter`: Filters wikia navigation while preserving main content
  - `SessionManager`: HTTP session handling with timeout and retry logic
  - `URLManager`: Queue management with deduplication and priority handling
  - `RateLimiter`: Per-domain request throttling with burst protection
  - `ContentSaver`: File-based storage with URL-to-filename mapping

### 2. **Data Processing Module** (`processor/`) - 🔄 PLANNED
- **Purpose**: Clean and structure extracted data
- **Components**:
  - `TextCleaner`: Removes wikia markup, navigation elements
  - `CharacterDetector`: Identifies character mentions in text
  - `ContentStructurer`: Organizes data into structured format
  - `DataValidator`: Ensures data quality and completeness

### 3. **LLM Analysis Module** (`analyzer/`) - 🔄 PLANNED
- **Purpose**: Extract relationships using AI analysis
- **Components**:
  - `RelationshipExtractor`: Uses LLM to identify character relationships
  - `ContextAnalyzer`: Determines relationship context and strength
  - `EntityLinker`: Links mentions to canonical character names
  - `PromptManager`: Manages and optimizes LLM prompts

### 4. **Relationship Mapping Module** (`mapper/`) - 🔄 PLANNED
- **Purpose**: Process and structure relationship data
- **Components**:
  - `RelationshipGraph`: Build graph structure of relationships
  - `RelationshipClassifier`: Categorize relationship types
  - `ConfidenceScorer`: Assign confidence scores to relationships
  - `ConflictResolver`: Handle conflicting relationship information

### 5. **Visualization Module** (`visualizer/`) - 🔄 PLANNED
- **Purpose**: Generate charts and visual representations
- **Components**:
  - `NetworkGraphGenerator`: Creates interactive network graphs
  - `RelationshipCharts`: Generates various chart types
  - `ExportManager`: Exports to different formats (JSON, CSV, SVG)
  - `InteractiveViewer`: Web-based relationship explorer

### 6. **Data Storage Module** (`storage/`) - ✅ PARTIAL (File-based implemented)
- **Purpose**: Persist and manage data
- **Components**:
  - `ContentSaver`: ✅ File-based storage with project organization
  - `CrawlState`: ✅ Session persistence for resumable crawls
  - `DatabaseManager`: 🔄 Handle database operations (planned)
  - `CacheManager`: 🔄 Cache frequently accessed data (planned)
  - `BackupManager`: 🔄 Data backup and recovery (planned)

## Technology Stack

- **Backend**: Python 3.13+ 
- **Web Crawling**: BeautifulSoup4 + aiohttp (async HTTP)
- **Testing**: pytest with comprehensive coverage (403+ tests)
- **Data Format**: JSON for structured data, YAML for configuration
- **Storage**: File-based with project isolation (database planned for Phase 2)
- **LLM Integration**: OpenAI API, Anthropic Claude API (planned)
- **Visualization**: NetworkX + Plotly/D3.js (planned)
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

### 🔄 Phase 2: Data Processing (NEXT)
1. Implement character detection and entity linking
2. Build text cleaning and content structuring
3. Create data validation and quality checks
4. Add content categorization and organization

### 🔄 Phase 3: LLM Analysis & Intelligence (PLANNED)
1. Integrate LLM API for relationship extraction
2. Build relationship graph data structure
3. Develop relationship classification system
4. Implement confidence scoring algorithms

### 🔄 Phase 4: Visualization & Interface (PLANNED)
1. Implement network graph generation
2. Create interactive web interface
3. Build export functionality
4. Add filtering and search capabilities

### 🔄 Phase 5: Optimization & Deployment (PLANNED)
1. Performance optimization and caching
2. Database integration and migration
3. Enhanced error handling and monitoring
4. Deployment setup and CI/CD

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
- **✅ Relationship-Aware**: Intelligent link discovery prioritizing character connections
- **✅ Wikia-Specialized**: Custom parsing for Fandom/Wikia site structures
- **✅ Test-Driven**: 403+ comprehensive tests ensuring reliability
- **✅ Developer-Friendly**: Manual testing interface and detailed logging
- **🔄 Configurable**: Easy adaptation to different wikia sites (planned)
- **🔄 Scalable**: Designed to handle large wikia sites (planned)
- **🔄 Interactive**: Web-based visualization and exploration (planned)

## Getting Started

### Prerequisites
```bash
Python 3.13+
pip install -e ".[dev]"  # Install with development dependencies
```

### Quick Start
```bash
# Manual testing interface
python test_crawler.py

# CLI interface (planned)
python main.py crawl <project_name> <wikia_url>
python main.py status <project_name>
```

### Development
```bash
# Run tests
python -m pytest tests/test_crawler/

# Run specific test file
python -m pytest tests/test_crawler/extraction/test_wikia_parser.py -v

# Code formatting
black src/ tests/
isort src/ tests/
```

## Configuration
Configuration uses YAML files with hierarchical overrides. The system respects:
- Global crawler settings (rate limits, user agent)
- Per-domain rate limiting overrides
- Project-specific configuration
- Wikia namespace and content filters

## Current Capabilities
The implemented Phase 1 crawler can:
1. **Crawl wikia sites** with ethical rate limiting and robots.txt compliance
2. **Extract structured content** including titles, links, categories, and infoboxes
3. **Discover character relationships** through intelligent link analysis
4. **Filter content** removing navigation while preserving main content
5. **Validate domains** ensuring single-wikia scope without cross-contamination
6. **Store data persistently** with project-based organization and resumable crawls
7. **Handle errors gracefully** with exponential backoff and retry logic

## Contributing
This project uses modern Python development practices:
- **Type hints** throughout the codebase
- **Comprehensive testing** with pytest
- **Code formatting** with black and isort
- **Modular architecture** for independent component development

## License
MIT License (see LICENSE file)