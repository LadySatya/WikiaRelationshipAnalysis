# Embedding Provider Interface Design

**Status**: Design Pattern
**Last Updated**: 2025-10-15

## Overview

This document describes the interface-based design for embedding generation, allowing seamless switching between local (sentence-transformers) and API-based (Voyage AI) embedding providers.

## Design Goals

1. **Prototype with Local**: Use free sentence-transformers during development/testing
2. **Production with API**: Swap to Voyage AI for better quality in production
3. **Zero Code Changes**: Switch providers via configuration only
4. **Cost Tracking**: Track costs regardless of provider
5. **Fallback Support**: Gracefully degrade to local if API unavailable

## Architecture

### Interface Pattern

```python
# Abstract base class for all embedding providers
class EmbeddingProvider(ABC):
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text string"""
        pass

    @abstractmethod
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (optimized)"""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Return embedding dimension size"""
        pass

    @abstractmethod
    def get_cost(self, num_tokens: int) -> float:
        """Calculate cost in USD for given token count"""
        pass
```

### Implementation Classes

#### 1. LocalEmbeddingProvider (sentence-transformers)

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Local embedding generation using sentence-transformers.

    Pros:
    - Free (no API costs)
    - Fast (runs locally)
    - No rate limits
    - Works offline

    Cons:
    - Lower quality than Voyage AI
    - Requires ~500MB model download
    - Uses local compute resources

    Models:
    - Default: "all-MiniLM-L6-v2" (384 dimensions, 80MB)
    - Better: "all-mpnet-base-v2" (768 dimensions, 420MB)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name

    def generate_embedding(self, text: str) -> List[float]:
        return self.model.encode(text).tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts).tolist()

    def get_dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def get_cost(self, num_tokens: int) -> float:
        return 0.0  # Free
```

#### 2. VoyageEmbeddingProvider (Voyage AI API)

```python
class VoyageEmbeddingProvider(EmbeddingProvider):
    """
    API-based embedding generation using Voyage AI.

    Pros:
    - Higher quality embeddings (recommended by Anthropic)
    - No local compute needed
    - Optimized for RAG use cases

    Cons:
    - Costs money (~$0.02 per 100 pages)
    - Requires API key
    - Requires internet connection
    - Rate limits apply

    Models:
    - voyage-3-lite: Fast, cheap, good quality (recommended)
    - voyage-3: Higher quality, more expensive
    """

    def __init__(self, api_key: str, model: str = "voyage-3-lite"):
        import voyageai
        self.client = voyageai.Client(api_key=api_key)
        self.model = model
        self.cost_per_million_tokens = 0.12  # voyage-3-lite pricing

    def generate_embedding(self, text: str) -> List[float]:
        result = self.client.embed([text], model=self.model)
        return result.embeddings[0]

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        result = self.client.embed(texts, model=self.model)
        return result.embeddings

    def get_dimension(self) -> int:
        return 1024  # voyage-3-lite dimension

    def get_cost(self, num_tokens: int) -> float:
        return (num_tokens / 1_000_000) * self.cost_per_million_tokens
```

### Factory Pattern

```python
class EmbeddingProviderFactory:
    """Factory to create embedding providers from configuration"""

    @staticmethod
    def create(config: Dict[str, Any]) -> EmbeddingProvider:
        provider_type = config.get("embedding_provider", "local")

        if provider_type == "local":
            model_name = config.get("local_model", "all-MiniLM-L6-v2")
            return LocalEmbeddingProvider(model_name=model_name)

        elif provider_type == "voyage":
            api_key = config.get("voyage_api_key") or os.getenv("VOYAGE_API_KEY")
            if not api_key:
                raise ValueError("Voyage AI API key required")
            model = config.get("voyage_model", "voyage-3-lite")
            return VoyageEmbeddingProvider(api_key=api_key, model=model)

        else:
            raise ValueError(f"Unknown provider: {provider_type}")
```

## Configuration

### config/processor_config.yaml

```yaml
processor:
  rag:
    # Embedding provider configuration
    embedding_provider: "local"  # "local" or "voyage"

    # Local provider settings (sentence-transformers)
    local_model: "all-MiniLM-L6-v2"  # Options: all-MiniLM-L6-v2, all-mpnet-base-v2

    # Voyage AI settings (requires VOYAGE_API_KEY env var)
    # voyage_model: "voyage-3-lite"  # Uncomment when ready to use

    # ... rest of config
```

### Environment Variables

```bash
# .env file
VOYAGE_API_KEY=your_voyage_api_key_here  # Only needed for Voyage AI
ANTHROPIC_API_KEY=your_anthropic_api_key_here  # For Claude LLM
```

## Usage Example

```python
# Initialize from config (no provider-specific code)
from src.processor.rag.embeddings import EmbeddingGenerator

config = load_config("config/processor_config.yaml")
generator = EmbeddingGenerator(config)

# Generate embeddings (works with any provider)
embedding = generator.generate_embedding("Aang is the Avatar")
embeddings = generator.generate_embeddings_batch([
    "Aang is the Avatar",
    "Katara is a waterbender"
])

# Track costs (returns 0.0 for local, actual cost for Voyage AI)
cost = generator.get_total_cost()
print(f"Embedding cost: ${cost:.4f}")
```

## Migration Path

### Phase 1: Prototype with Local (Current)
```yaml
embedding_provider: "local"
local_model: "all-MiniLM-L6-v2"
```

**Benefits**:
- Free
- Fast iteration
- No API key setup needed

### Phase 2: Test with Voyage AI (After MVP)
```yaml
embedding_provider: "voyage"
voyage_model: "voyage-3-lite"
```

**Benefits**:
- Better quality embeddings
- Still cheap (~$0.02 per project)
- Recommended by Anthropic

### Phase 3: Hybrid (Future Optimization)
```python
# Use local for development/testing, Voyage AI for production
if os.getenv("ENVIRONMENT") == "production":
    config["embedding_provider"] = "voyage"
else:
    config["embedding_provider"] = "local"
```

## Implementation Checklist

- [ ] Create `EmbeddingProvider` abstract base class
- [ ] Implement `LocalEmbeddingProvider` with sentence-transformers
- [ ] Implement `VoyageEmbeddingProvider` (stub for now, commented out)
- [ ] Create `EmbeddingProviderFactory`
- [ ] Create `EmbeddingGenerator` wrapper class
- [ ] Add configuration support
- [ ] Write unit tests for both providers
- [ ] Add cost tracking
- [ ] Document switching process

## Testing Strategy

### Unit Tests (Both Providers)

```python
class TestLocalEmbeddingProvider:
    def test_generate_single_embedding(self):
        provider = LocalEmbeddingProvider()
        embedding = provider.generate_embedding("test")
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
        assert isinstance(embedding, list)

    def test_cost_is_zero(self):
        provider = LocalEmbeddingProvider()
        assert provider.get_cost(1000) == 0.0

class TestVoyageEmbeddingProvider:
    @pytest.mark.unit
    def test_generate_embedding_mocked(self, mock_voyage_api):
        provider = VoyageEmbeddingProvider(api_key="test")
        embedding = provider.generate_embedding("test")
        assert len(embedding) == 1024

    @pytest.mark.integration
    def test_generate_embedding_real(self):
        # Only runs if VOYAGE_API_KEY is set
        if not os.getenv("VOYAGE_API_KEY"):
            pytest.skip("No API key")
        provider = VoyageEmbeddingProvider(api_key=os.getenv("VOYAGE_API_KEY"))
        embedding = provider.generate_embedding("test")
        assert len(embedding) == 1024
```

## Performance Comparison

| Provider | Model | Dimension | Speed (100 chunks) | Cost (100 chunks) | Quality |
|----------|-------|-----------|-------------------|-------------------|---------|
| Local | all-MiniLM-L6-v2 | 384 | ~2s | $0.00 | Good |
| Local | all-mpnet-base-v2 | 768 | ~5s | $0.00 | Better |
| Voyage AI | voyage-3-lite | 1024 | ~3s | ~$0.02 | Best |
| Voyage AI | voyage-3 | 1024 | ~5s | ~$0.05 | Excellent |

**Recommendation**: Start with `all-MiniLM-L6-v2` for prototyping, switch to `voyage-3-lite` for production.

## Notes

- Interface design allows adding more providers later (OpenAI embeddings, Cohere, etc.)
- Cost tracking built into interface for budget monitoring
- Provider switching requires no code changes (configuration only)
- Local provider perfect for development, API provider better for production quality

---

**Next Steps**:
1. Implement `LocalEmbeddingProvider` first (Week 2)
2. Add Voyage AI stub with clear TODOs (Week 2)
3. Test with local embeddings (Week 2-4)
4. Switch to Voyage AI when ready for production quality (Week 5+)
