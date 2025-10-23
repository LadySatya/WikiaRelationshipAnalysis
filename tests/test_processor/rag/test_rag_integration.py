"""
Integration tests for RAG Pipeline - end-to-end workflow.

This module tests the complete RAG pipeline from indexing to query:
1. ContentChunker splits documents into chunks
2. EmbeddingGenerator creates embeddings
3. VectorStore stores and retrieves chunks
4. RAGRetriever performs semantic search
5. QueryEngine combines retrieval + LLM for final answers

These are integration tests using real components (not mocks).
"""
import pytest
import tempfile
import shutil
from typing import List, Dict, Any

# Mark all tests as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def temp_vector_store(tmp_path):
    """Create temporary directory for vector store."""
    return tmp_path


@pytest.fixture
def sample_documents() -> List[Dict[str, Any]]:
    """Sample wiki documents for testing - matches ContentChunker.chunk_page() format."""
    return [
        {
            "url": "https://example.com/aang",
            "content": {
                "title": "Aang",
                "main_content": "Aang is the protagonist of Avatar: The Last Airbender. "
                               "He is the Avatar and last surviving Air Nomad. "
                               "Aang was frozen in an iceberg for 100 years and was found by Katara and Sokka. "
                               "He mastered all four elements: air, water, earth, and fire.",
                "namespace": "Character"
            }
        },
        {
            "url": "https://example.com/katara",
            "content": {
                "title": "Katara",
                "main_content": "Katara is a waterbender from the Southern Water Tribe. "
                               "She is one of Aang's closest friends and teachers. "
                               "Katara taught Aang waterbending and later became his wife. "
                               "She is known for her powerful healing abilities.",
                "namespace": "Character"
            }
        },
        {
            "url": "https://example.com/zuko",
            "content": {
                "title": "Zuko",
                "main_content": "Zuko is the prince of the Fire Nation. "
                               "He was initially an antagonist hunting the Avatar. "
                               "Zuko eventually joined Team Avatar and taught Aang firebending. "
                               "He later became the Fire Lord and helped restore balance.",
                "namespace": "Character"
            }
        }
    ]


def prepare_vector_store(temp_dir, sample_documents, project_name):
    """Helper function to chunk, embed, and store documents."""
    from src.processor.core.content_chunker import ContentChunker
    from src.processor.rag.embeddings import EmbeddingGenerator
    from src.processor.rag.vector_store import VectorStore

    # Initialize components
    chunker = ContentChunker()
    embedding_gen = EmbeddingGenerator(provider="local")
    vector_store = VectorStore(
        project_name=project_name,
        persist_directory=temp_dir
    )

    # Process documents
    all_chunks = []
    for doc in sample_documents:
        chunks = chunker.chunk_page(doc)
        all_chunks.extend(chunks)

    # Generate embeddings
    texts = [chunk["text"] for chunk in all_chunks]
    embeddings = embedding_gen.generate_embeddings(texts)

    # Combine chunks with embeddings for storage
    chunks_with_embeddings = []
    for i, chunk in enumerate(all_chunks):
        chunks_with_embeddings.append({
            "text": chunk["text"],
            "embedding": embeddings[i],
            "metadata": chunk["metadata"]
        })

    # Store in vector database
    vector_store.add_documents(chunks_with_embeddings)

    return vector_store, all_chunks


class TestRAGPipelineIndexing:
    """Test end-to-end indexing workflow."""

    def test_full_indexing_pipeline(self, temp_vector_store, sample_documents):
        """Test complete indexing: chunk → embed → store."""
        vector_store, all_chunks = prepare_vector_store(
            temp_vector_store,
            sample_documents,
            "test_rag_integration"
        )

        # Verify storage
        assert vector_store.has_documents()
        stats = vector_store.get_collection_stats()
        assert stats["count"] == len(all_chunks)
        assert stats["count"] == 3  # 3 documents, each produces 1 chunk


class TestRAGPipelineRetrieval:
    """Test end-to-end retrieval workflow."""

    def test_full_retrieval_pipeline(self, temp_vector_store, sample_documents):
        """Test complete retrieval: query → embed → search → rank."""
        from src.processor.rag.retriever import RAGRetriever

        # Setup: Index sample documents first
        prepare_vector_store(temp_vector_store, sample_documents, "test_rag_retrieval")

        # Test: Retrieve relevant chunks
        retriever = RAGRetriever(
            project_name="test_rag_retrieval",
            vector_store_path=temp_vector_store
        )

        results = retriever.retrieve("Who is Aang?", k=3)

        # Verify results
        assert len(results) > 0
        assert len(results) <= 3
        assert "Aang" in results[0]["text"]
        assert "distance" in results[0]
        assert "metadata" in results[0]
        assert "url" in results[0]["metadata"]

    def test_retrieval_with_metadata_filter(self, temp_vector_store, sample_documents):
        """Test retrieval with metadata filtering."""
        from src.processor.rag.retriever import RAGRetriever

        # Setup: Index documents
        prepare_vector_store(temp_vector_store, sample_documents, "test_rag_filter")

        # Test: Filter by namespace
        retriever = RAGRetriever(
            project_name="test_rag_filter",
            vector_store_path=temp_vector_store
        )

        results = retriever.retrieve(
            "characters",
            k=10,
            metadata_filter={"namespace": "Character"}
        )

        # Verify all results match filter
        assert len(results) > 0
        for result in results:
            assert result["metadata"]["namespace"] == "Character"

    def test_context_building(self, temp_vector_store, sample_documents):
        """Test building formatted context from retrieved chunks."""
        from src.processor.rag.retriever import RAGRetriever

        # Setup: Index documents
        prepare_vector_store(temp_vector_store, sample_documents, "test_context")

        # Test: Build context
        retriever = RAGRetriever(
            project_name="test_context",
            vector_store_path=temp_vector_store
        )

        results = retriever.retrieve("Who is Aang?", k=2)
        context = retriever.build_context(results)

        # Verify context formatting
        assert isinstance(context, str)
        assert len(context) > 0
        assert "Retrieved Information" in context
        assert "Chunk" in context
        assert "Source:" in context


class TestRAGPipelineQuery:
    """Test end-to-end query workflow with mocked LLM."""

    def test_full_query_pipeline_with_mock_llm(self, temp_vector_store, sample_documents):
        """Test complete query: retrieve → context → LLM (mocked)."""
        from unittest.mock import patch, MagicMock
        from src.processor.rag.query_engine import QueryEngine

        # Setup: Index documents
        vector_store, _ = prepare_vector_store(
            temp_vector_store,
            sample_documents,
            "test_query"
        )

        # Test: Query with mocked LLM
        with patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Aang is the Avatar and protagonist of the series."
            mock_llm.get_usage_stats.return_value = {
                "total_input_tokens": 100,
                "total_output_tokens": 20,
                "estimated_cost_usd": 0.001
            }
            mock_llm_class.return_value = mock_llm

            # Patch retriever's VectorStore to use our indexed one
            with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class:
                mock_vs_class.return_value = vector_store

                engine = QueryEngine(project_name="test_query")

                # Execute query
                response = engine.query("Who is Aang?", k=3)

                # Verify response
                assert isinstance(response, str)
                assert len(response) > 0
                assert "Aang" in response

                # Verify LLM was called with correct parameters
                assert mock_llm.generate.called
                call_kwargs = mock_llm.generate.call_args.kwargs
                assert "prompt" in call_kwargs
                assert "system_prompt" in call_kwargs

    def test_detailed_query_response(self, temp_vector_store, sample_documents):
        """Test detailed query response with sources and metadata."""
        from unittest.mock import patch, MagicMock
        from src.processor.rag.query_engine import QueryEngine

        # Setup: Index documents
        vector_store, _ = prepare_vector_store(
            temp_vector_store,
            sample_documents,
            "test_detailed"
        )

        # Test: Detailed query
        with patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Katara is a waterbender from the Southern Water Tribe."
            mock_llm.get_usage_stats.return_value = {
                "total_input_tokens": 150,
                "total_output_tokens": 30,
                "estimated_cost_usd": 0.002
            }
            mock_llm_class.return_value = mock_llm

            with patch("src.processor.rag.retriever.VectorStore") as mock_vs_class:
                mock_vs_class.return_value = vector_store

                engine = QueryEngine(project_name="test_detailed")
                response = engine.query_detailed("Who is Katara?", k=2)

                # Verify response structure
                assert "query" in response
                assert "answer" in response
                assert "sources" in response
                assert "usage" in response

                # Verify sources
                assert len(response["sources"]) > 0
                assert "text" in response["sources"][0]
                assert "url" in response["sources"][0]
                assert "distance" in response["sources"][0]

                # Verify usage stats
                assert "total_input_tokens" in response["usage"]
                assert "estimated_cost_usd" in response["usage"]
