"""
Tests for QueryEngine - RAG query system combining retrieval and LLM.

Following TDD methodology: write tests first, then implement.
This module tests the QueryEngine class which handles:
- End-to-end RAG queries (retrieval + LLM generation)
- Integration of RAGRetriever and LLMClient
- Context building and prompt formatting
- Response generation with source tracking
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestQueryEngineInitialization:
    """Test QueryEngine initialization."""

    def test_init_with_project_name(self):
        """QueryEngine should initialize with project name."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever"), \
             patch("src.processor.rag.query_engine.LLMClient"):

            engine = QueryEngine(project_name="avatar_wiki")

            assert engine.project_name == "avatar_wiki"

    def test_init_creates_retriever(self):
        """QueryEngine should create RAGRetriever for project."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient"):

            engine = QueryEngine(project_name="test_wiki")

            # Should create retriever with project name
            mock_retriever_class.assert_called_once_with(project_name="test_wiki")

    def test_init_creates_llm_client(self):
        """QueryEngine should create LLMClient."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever"), \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            engine = QueryEngine(project_name="test_wiki")

            # Should create LLMClient
            mock_llm_class.assert_called_once()


class TestQueryEngineQuery:
    """Test RAG query execution."""

    def test_query_basic(self):
        """QueryEngine should execute full RAG query (retrieve + generate)."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            # Mock retriever
            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = [
                {"id": "chunk1", "text": "Aang is the Avatar", "metadata": {"url": "url1"}, "distance": 0.1}
            ]
            mock_retriever.build_context.return_value = "Context: Aang is the Avatar"
            mock_retriever_class.return_value = mock_retriever

            # Mock LLM client
            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Aang is the protagonist of Avatar: The Last Airbender."
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            response = engine.query("Who is Aang?")

            # Should retrieve chunks
            mock_retriever.retrieve.assert_called_once_with(query="Who is Aang?", k=10, metadata_filter=None)

            # Should build context
            mock_retriever.build_context.assert_called_once()

            # Should generate response
            mock_llm.generate.assert_called_once()

            # Should return response
            assert "Aang" in response

    def test_query_with_custom_k(self):
        """QueryEngine should support custom k for retrieval."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = []
            mock_retriever.build_context.return_value = "No info"
            mock_retriever_class.return_value = mock_retriever

            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Response"
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            engine.query("Test", k=20)

            # Should pass k to retriever
            call_args = mock_retriever.retrieve.call_args
            assert call_args[1]["k"] == 20

    def test_query_with_metadata_filter(self):
        """QueryEngine should support metadata filtering."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = []
            mock_retriever.build_context.return_value = "No info"
            mock_retriever_class.return_value = mock_retriever

            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Response"
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            filter_dict = {"namespace": "Character"}
            engine.query("Test", metadata_filter=filter_dict)

            # Should pass filter to retriever
            call_args = mock_retriever.retrieve.call_args
            assert call_args[1]["metadata_filter"] == filter_dict

    def test_query_uses_system_prompt(self):
        """QueryEngine should use default system prompt for RAG context."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = []
            mock_retriever.build_context.return_value = "Context"
            mock_retriever_class.return_value = mock_retriever

            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Response"
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            engine.query("Test")

            # Should use system prompt
            call_kwargs = mock_llm.generate.call_args[1]
            assert "system_prompt" in call_kwargs
            assert call_kwargs["system_prompt"] is not None

    def test_query_includes_context_in_prompt(self):
        """QueryEngine should include retrieved context in LLM prompt."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = [
                {"text": "Important context", "metadata": {}, "distance": 0.1}
            ]
            mock_retriever.build_context.return_value = "Retrieved: Important context"
            mock_retriever_class.return_value = mock_retriever

            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Answer"
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            engine.query("Test query")

            # LLM prompt should include context
            call_args = mock_llm.generate.call_args
            prompt = call_args.kwargs['prompt']  # Access keyword argument
            assert "Important context" in prompt or "context" in prompt.lower()


class TestQueryEngineResponse:
    """Test response formatting and metadata."""

    def test_query_returns_detailed_response(self):
        """QueryEngine should return detailed response with metadata."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = [
                {"id": "chunk1", "text": "Context", "metadata": {"url": "url1"}, "distance": 0.1}
            ]
            mock_retriever.build_context.return_value = "Context"
            mock_retriever_class.return_value = mock_retriever

            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Generated answer"
            mock_llm.get_usage_stats.return_value = {
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "estimated_cost_usd": 0.001
            }
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            response = engine.query_detailed("Who is Aang?")

            # Should have answer field
            assert "answer" in response
            assert response["answer"] == "Generated answer"

            # Should have sources field
            assert "sources" in response
            assert len(response["sources"]) == 1

            # Should have usage stats
            assert "usage" in response

    def test_query_detailed_includes_query(self):
        """QueryEngine detailed response should include original query."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = []
            mock_retriever.build_context.return_value = ""
            mock_retriever_class.return_value = mock_retriever

            mock_llm = MagicMock()
            mock_llm.generate.return_value = "Answer"
            mock_llm.get_usage_stats.return_value = {}
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            response = engine.query_detailed("Who is Naruto?")

            assert "query" in response
            assert response["query"] == "Who is Naruto?"


class TestQueryEngineEdgeCases:
    """Test edge cases and error handling."""

    def test_query_empty_string(self):
        """QueryEngine should handle empty queries."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever"), \
             patch("src.processor.rag.query_engine.LLMClient"):

            engine = QueryEngine(project_name="test_wiki")

            with pytest.raises(ValueError, match="query cannot be empty"):
                engine.query("")

    def test_query_no_results_from_retrieval(self):
        """QueryEngine should handle case when no relevant chunks found."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever") as mock_retriever_class, \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = []
            mock_retriever.build_context.return_value = "No relevant information found."
            mock_retriever_class.return_value = mock_retriever

            mock_llm = MagicMock()
            mock_llm.generate.return_value = "I don't have information about that."
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            response = engine.query("Unknown topic")

            # Should still generate response
            assert isinstance(response, str)
            assert len(response) > 0

    def test_get_usage_stats(self):
        """QueryEngine should provide access to LLM usage stats."""
        from src.processor.rag.query_engine import QueryEngine

        with patch("src.processor.rag.query_engine.RAGRetriever"), \
             patch("src.processor.rag.query_engine.LLMClient") as mock_llm_class:

            mock_llm = MagicMock()
            mock_llm.get_usage_stats.return_value = {
                "total_tokens": 150,
                "estimated_cost_usd": 0.002
            }
            mock_llm_class.return_value = mock_llm

            engine = QueryEngine(project_name="test_wiki")
            stats = engine.get_usage_stats()

            assert "total_tokens" in stats
            assert "estimated_cost_usd" in stats
