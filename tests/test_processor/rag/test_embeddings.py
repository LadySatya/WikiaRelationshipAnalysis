"""
Tests for EmbeddingGenerator - generates vector embeddings from text chunks.

Following TDD methodology: write tests first, then implement.
"""
import pytest
import numpy as np
import sys
from typing import List
from unittest.mock import Mock, patch, MagicMock


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# Create a fake voyageai module for testing
fake_voyageai = MagicMock()
sys.modules['voyageai'] = fake_voyageai


class TestEmbeddingGeneratorInitialization:
    """Test EmbeddingGenerator initialization and configuration."""

    def test_init_with_local_provider(self):
        """EmbeddingGenerator should initialize with local sentence-transformers model."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(provider="local", model_name="all-MiniLM-L6-v2")

        assert generator.provider == "local"
        assert generator.model_name == "all-MiniLM-L6-v2"

    def test_init_with_voyage_provider(self):
        """EmbeddingGenerator should support Voyage AI provider configuration."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(provider="voyage", model_name="voyage-3-lite")

        assert generator.provider == "voyage"
        assert generator.model_name == "voyage-3-lite"

    def test_init_validates_provider(self):
        """EmbeddingGenerator should validate provider is supported."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with pytest.raises(ValueError, match="provider must be one of"):
            EmbeddingGenerator(provider="invalid")

    def test_init_loads_local_model_lazily(self):
        """EmbeddingGenerator should not load model during init (lazy loading)."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(provider="local")

        # Model should be None until first use (lazy loading)
        assert generator._model is None

    def test_init_with_default_parameters(self):
        """EmbeddingGenerator should use sensible defaults from config."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator()

        # Should default to local provider as per config
        assert generator.provider == "local"
        assert generator.model_name == "all-MiniLM-L6-v2"


class TestEmbeddingGeneratorLocalEmbeddings:
    """Test local embedding generation using sentence-transformers."""

    def test_generate_embedding_single_text(self):
        """EmbeddingGenerator should generate embedding vector for single text."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        # Mock at the import location within the function
        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            # Mock the model to return a fake embedding
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(provider="local")
            embedding = generator.generate_embedding("Test text")

            # Should return numpy array
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (3,)
            mock_model.encode.assert_called_once_with("Test text", convert_to_numpy=True)

    def test_generate_embeddings_batch(self):
        """EmbeddingGenerator should generate embeddings for multiple texts in batch."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            # Mock the model to return fake embeddings
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6]
            ])
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(provider="local")
            texts = ["Text one", "Text two"]
            embeddings = generator.generate_embeddings(texts)

            # Should return list of numpy arrays
            assert isinstance(embeddings, list)
            assert len(embeddings) == 2
            assert all(isinstance(emb, np.ndarray) for emb in embeddings)
            mock_model.encode.assert_called_once()

    def test_generate_embedding_loads_model_once(self):
        """EmbeddingGenerator should load model only once and reuse it."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(provider="local")

            # Generate multiple embeddings
            generator.generate_embedding("Text 1")
            generator.generate_embedding("Text 2")
            generator.generate_embedding("Text 3")

            # Model should only be loaded once
            assert mock_st.call_count == 1

    def test_generate_embedding_empty_text(self):
        """EmbeddingGenerator should handle empty text gracefully."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            # Empty text should still produce an embedding (model behavior)
            mock_model.encode.return_value = np.array([0.0, 0.0, 0.0])
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(provider="local")
            embedding = generator.generate_embedding("")

            assert isinstance(embedding, np.ndarray)
            mock_model.encode.assert_called_once_with("", convert_to_numpy=True)


class TestEmbeddingGeneratorVoyageEmbeddings:
    """Test Voyage AI embedding generation."""

    def test_generate_embedding_voyage_single_text(self):
        """EmbeddingGenerator should generate embedding using Voyage API."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("voyageai.Client") as mock_client_class:
            # Mock Voyage client
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.embeddings = [[0.1, 0.2, 0.3]]
            mock_client.embed.return_value = mock_response
            mock_client_class.return_value = mock_client

            generator = EmbeddingGenerator(provider="voyage", model_name="voyage-3-lite")
            embedding = generator.generate_embedding("Test text")

            # Should return numpy array from Voyage response
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (3,)
            mock_client.embed.assert_called_once()

    def test_generate_embeddings_voyage_batch(self):
        """EmbeddingGenerator should batch multiple texts for Voyage API."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("voyageai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            mock_client.embed.return_value = mock_response
            mock_client_class.return_value = mock_client

            generator = EmbeddingGenerator(provider="voyage")
            texts = ["Text one", "Text two"]
            embeddings = generator.generate_embeddings(texts)

            # Should return list of numpy arrays
            assert isinstance(embeddings, list)
            assert len(embeddings) == 2
            mock_client.embed.assert_called_once_with(texts, model=generator.model_name)

    def test_voyage_requires_api_key(self):
        """EmbeddingGenerator should require VOYAGE_API_KEY for Voyage provider."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("voyageai.Client") as mock_client_class:
            # Simulate missing API key
            mock_client_class.side_effect = Exception("API key required")

            generator = EmbeddingGenerator(provider="voyage")

            with pytest.raises(Exception, match="API key"):
                generator.generate_embedding("Test")


class TestEmbeddingGeneratorChunkProcessing:
    """Test processing chunked data with metadata."""

    def test_embed_chunks_with_metadata(self):
        """EmbeddingGenerator should add embeddings to chunks while preserving metadata."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            # Return different embeddings for each chunk
            mock_model.encode.return_value = np.array([
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6]
            ])
            mock_st.return_value = mock_model

            chunks = [
                {
                    "text": "Aang is the Avatar.",
                    "metadata": {"url": "https://example.com", "chunk_index": 0}
                },
                {
                    "text": "Katara is a waterbender.",
                    "metadata": {"url": "https://example.com", "chunk_index": 1}
                }
            ]

            generator = EmbeddingGenerator(provider="local")
            embedded_chunks = generator.embed_chunks(chunks)

            # Should preserve original structure and add embeddings
            assert len(embedded_chunks) == 2
            assert embedded_chunks[0]["text"] == "Aang is the Avatar."
            assert embedded_chunks[0]["metadata"]["chunk_index"] == 0
            assert "embedding" in embedded_chunks[0]
            assert isinstance(embedded_chunks[0]["embedding"], np.ndarray)

    def test_embed_chunks_batch_efficiency(self):
        """EmbeddingGenerator should batch process chunks for efficiency."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                [0.7, 0.8, 0.9]
            ])
            mock_st.return_value = mock_model

            chunks = [
                {"text": f"Text {i}", "metadata": {"chunk_index": i}}
                for i in range(3)
            ]

            generator = EmbeddingGenerator(provider="local")
            generator.embed_chunks(chunks)

            # Should call encode once with all texts (batch processing)
            assert mock_model.encode.call_count == 1
            call_args = mock_model.encode.call_args[0][0]
            assert len(call_args) == 3  # All texts in one batch

    def test_embed_chunks_empty_list(self):
        """EmbeddingGenerator should handle empty chunk list gracefully."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(provider="local")
        embedded_chunks = generator.embed_chunks([])

        assert embedded_chunks == []


class TestEmbeddingGeneratorProperties:
    """Test embedding properties and dimensions."""

    def test_get_embedding_dimension_local(self):
        """EmbeddingGenerator should report correct embedding dimension for local model."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(provider="local", model_name="all-MiniLM-L6-v2")
            dimension = generator.embedding_dimension

            # Should query the model for dimension
            assert dimension == 384

    def test_get_embedding_dimension_voyage(self):
        """EmbeddingGenerator should report correct embedding dimension for Voyage model."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("voyageai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            # voyage-3-lite produces 1024-dimensional embeddings
            mock_response.embeddings = [[0.1] * 1024]
            mock_client.embed.return_value = mock_response
            mock_client_class.return_value = mock_client

            generator = EmbeddingGenerator(provider="voyage", model_name="voyage-3-lite")
            dimension = generator.embedding_dimension

            # Should discover dimension by generating test embedding
            assert dimension == 1024


class TestEmbeddingGeneratorEdgeCases:
    """Test edge cases and error handling."""

    def test_generate_embedding_with_unicode(self):
        """EmbeddingGenerator should handle Unicode text correctly."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(provider="local")
            text = "Aang uses 气 (air) bending. Katara uses 水 (water)."
            embedding = generator.generate_embedding(text)

            assert isinstance(embedding, np.ndarray)
            # Verify the Unicode text was passed correctly
            mock_model.encode.assert_called_once()
            assert "气" in mock_model.encode.call_args[0][0]

    def test_generate_embeddings_large_batch(self):
        """EmbeddingGenerator should handle large batches of texts."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            # Simulate 100 embeddings
            mock_model.encode.return_value = np.random.rand(100, 384)
            mock_st.return_value = mock_model

            generator = EmbeddingGenerator(provider="local")
            texts = [f"Text {i}" for i in range(100)]
            embeddings = generator.generate_embeddings(texts)

            assert len(embeddings) == 100
            assert all(isinstance(emb, np.ndarray) for emb in embeddings)

    def test_model_loading_error_handling(self):
        """EmbeddingGenerator should handle model loading errors gracefully."""
        from src.processor.rag.embeddings import EmbeddingGenerator

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            # Simulate model loading failure
            mock_st.side_effect = Exception("Failed to download model")

            generator = EmbeddingGenerator(provider="local")

            with pytest.raises(Exception, match="Failed to download model"):
                generator.generate_embedding("Test")
