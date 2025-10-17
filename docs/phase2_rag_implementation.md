# Phase 2: RAG-Based Character Analysis

**Status**: ✅ COMPLETE - Full RAG pipeline validated with real data
**Updated**: 2025-10-17 (Completed)

## Quick Start

**Installed**: ChromaDB, Anthropic (Claude), sentence-transformers (local embeddings for prototyping), tiktoken
**Strategy**: Prototype with free local embeddings → swap to Voyage AI for production (interface-based, zero code changes)
**Cost**: ~$1.70 per 100 pages (using Claude Haiku)

### Progress (COMPLETED 2025-10-17)

**All Components Implemented** ✅:
- `src/processor/core/content_chunker.py` - Text chunking with metadata (16 tests)
- `src/processor/config.py` - Centralized YAML config loader (81% coverage)
- `src/processor/rag/embeddings.py` - Embedding generation (20 tests, 91% coverage)
- `src/processor/rag/vector_store.py` - ChromaDB integration (38 tests, 91% coverage)
- `src/processor/rag/retriever.py` - Semantic search (12 tests, 95% coverage)
- `src/processor/rag/query_engine.py` - RAG query interface (13 tests, 100% coverage)
- `src/processor/llm/llm_client.py` - Claude API wrapper (20 tests, 98% coverage)
- `config/processor_config.yaml` - Full configuration file

**Validation**:
- 6 integration tests passing (end-to-end RAG pipeline)
- Validated with real Phase 1 crawler data (97k+ char pages)
- Type safety: All components pass mypy checks
- See: `scripts/validate_phase2_with_real_data.py`

### Key Decisions Made
- **Centralized Config**: Created `ProcessorConfig` singleton - all components use `get_config()` instead of reading YAML directly
- **Dynamic Dimensions**: Embedding dimensions queried from models at runtime (no hardcoded magic numbers)
- **Proper Mocking**: All tests mock external dependencies - no real model downloads or API calls in unit tests
- **Test Debugging Rules**: Added global prompt at `~/.config/claude/prompt.md` with test failure investigation protocol

---

## Architecture Overview

**RAG Flow**: Crawled pages → Chunk text → Generate embeddings → Store in ChromaDB → Semantic search → Claude analyzes → Character profiles

**Components** (`src/processor/`):
- `core/content_chunker.py` - Split pages into chunks
- `rag/embeddings.py` - Generate embeddings (local or Voyage AI via interface)
- `rag/vector_store.py` - ChromaDB wrapper
- `rag/retriever.py` - Semantic search
- `rag/query_engine.py` - RAG queries (retriever + Claude)
- `analysis/character_extractor.py` - Discover characters
- `analysis/profile_builder.py` - Build profiles
- `llm/llm_client.py` - Claude API wrapper

## Embedding Provider Strategy

**Interface-based design** allows swapping providers without code changes:

```python
# Abstract interface
class EmbeddingProvider(ABC):
    def generate_embedding(text: str) -> List[float]
    def get_cost(num_tokens: int) -> float

# Implementations
LocalEmbeddingProvider   # sentence-transformers (free, prototyping)
VoyageEmbeddingProvider  # Voyage AI (production, $0.02 per 100 pages)
```

**Config-based switching** (`config/processor_config.yaml`):
```yaml
embedding_provider: "local"  # or "voyage"
local_model: "all-MiniLM-L6-v2"
```

See `embedding_provider_interface.md` for full design details.

---

## Implementation Timeline (COMPLETED)

**TDD approach**: All components developed with tests first, followed by implementation.

### Phase 2a: Core RAG Pipeline ✅ COMPLETE (Oct 15-17, 2025)
- ✅ Create `config/processor_config.yaml` (chunking, embeddings, vector store settings)
- ✅ **ProcessorConfig**: Centralized config management (singleton pattern)
- ✅ **ContentChunker**: Split pages into chunks with metadata (TDD, 16 tests)
- ✅ **EmbeddingGenerator**: Local + Voyage AI support with dynamic dimensions (TDD, 20 tests)
- ✅ **VectorStore**: ChromaDB wrapper with security validation (TDD, 38 tests)
- ✅ **LLMClient**: Claude API wrapper with cost tracking (TDD, 20 tests)
- ✅ **RAGRetriever**: Semantic search (TDD, 12 tests)
- ✅ **QueryEngine**: Combine retriever + LLM (TDD, 13 tests)
- ✅ **Integration tests**: End-to-end RAG pipeline (6 tests)
- ✅ **Validation**: Tested with real Phase 1 crawler data (97k+ char pages)

### Phase 2b: Character Analysis 📋 NEXT
- **CharacterExtractor**: Discover characters via RAG (TDD)
- **ProfileBuilder**: Build profiles per character (TDD)
- **Processor**: Main orchestrator (TDD)
- **Integration test**: Full pipeline on Avatar data

### Phase 2c: CLI & Polish 📋 FUTURE
- Add CLI commands to `main.py` (index, discover, build-profile, query)
- Progress tracking and cost reporting
- Final validation on 100+ pages

**Test Strategy**:
- Unit tests (`pytest -m unit`): Mock dependencies, fast
- Integration tests (`pytest -m integration`): Real ChromaDB/Claude, slower

**Cost**: ~$1.70 per 100 pages + 50 characters (Claude Haiku pricing)

---

## Configuration Example

`config/processor_config.yaml`:
```yaml
processor:
  rag:
    chunk_size: 500
    chunk_overlap: 50
    embedding_provider: "local"  # or "voyage" for production
    local_model: "all-MiniLM-L6-v2"
    vector_store_path: "data/vector_stores"
    default_k: 10
    llm_model: "claude-3-5-haiku-20241022"
  character_discovery:
    min_mentions: 3
    confidence_threshold: 0.7
```

Environment variables (`.env`):
```bash
ANTHROPIC_API_KEY=your_key_here
# VOYAGE_API_KEY=your_key_here  # For production embeddings
```
