"""
QueryEngine - RAG query system combining retrieval and LLM generation.

This module provides the main interface for RAG queries. It combines semantic
search (via RAGRetriever) with LLM generation (via LLMClient) to answer
questions based on retrieved wiki content.
"""
from typing import Dict, Any, Optional, List

from .retriever import RAGRetriever
from ..llm.llm_client import LLMClient


class QueryEngine:
    """
    End-to-end RAG query engine.

    Combines retrieval and generation to answer questions using wiki content:
    1. Retrieves relevant chunks using semantic search
    2. Builds context from retrieved chunks
    3. Generates answer using LLM with context

    Args:
        project_name: Name of the wikia project

    Example:
        >>> engine = QueryEngine(project_name="avatar_wiki")
        >>>
        >>> # Simple query
        >>> answer = engine.query("Who is Aang?")
        >>> print(answer)
        "Aang is the protagonist of Avatar: The Last Airbender..."
        >>>
        >>> # Detailed query with metadata
        >>> response = engine.query_detailed("Who is Aang?", k=5)
        >>> print(response["answer"])
        >>> print(f"Sources: {len(response['sources'])}")
        >>> print(f"Cost: ${response['usage']['estimated_cost_usd']:.4f}")
    """

    # Default system prompt for RAG queries
    DEFAULT_SYSTEM_PROMPT = """You are a helpful assistant analyzing wiki content.

Your task is to answer questions based ONLY on the provided context from the wiki.

Guidelines:
- Answer accurately based on the retrieved information
- If the context doesn't contain relevant information, say so
- Do not make up information beyond what's in the context
- Cite sources when possible by mentioning page names
- Keep answers clear and concise
"""

    def __init__(self, project_name: str) -> None:
        """
        Initialize QueryEngine for a specific project.

        Args:
            project_name: Name of the wikia project
        """
        self.project_name = project_name

        # Initialize retriever for semantic search
        self.retriever = RAGRetriever(project_name=project_name)

        # Initialize LLM client for generation
        self.llm_client = LLMClient()

    def query(
        self,
        query: str,
        k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Execute RAG query and return generated answer.

        Args:
            query: User question
            k: Number of chunks to retrieve (default: 10)
            metadata_filter: Optional metadata filter (e.g., {"namespace": "Character"})
            system_prompt: Optional custom system prompt (default: DEFAULT_SYSTEM_PROMPT)

        Returns:
            Generated answer as string

        Raises:
            ValueError: If query is empty
        """
        # Validate query
        if not query or not query.strip():
            raise ValueError("query cannot be empty")

        # Retrieve relevant chunks
        chunks = self.retriever.retrieve(
            query=query.strip(),
            k=k,
            metadata_filter=metadata_filter
        )

        # Build context from chunks
        context = self.retriever.build_context(chunks)

        # Build prompt with context and query
        prompt = f"""{context}

Question: {query.strip()}

Please answer the question based on the information provided above."""

        # Generate answer using LLM
        answer = self.llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
            temperature=0.3,  # Lower temperature for more factual responses
            max_tokens=1024
        )

        return answer

    def query_detailed(
        self,
        query: str,
        k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        use_citations: bool = False
    ) -> Dict[str, Any]:
        """
        Execute RAG query and return detailed response with metadata.

        Args:
            query: User question
            k: Number of chunks to retrieve (default: 10)
            metadata_filter: Optional metadata filter
            use_citations: Enable citation tracking (default: False)

        Returns:
            Dictionary with structure:
                {
                    "query": "Who is Aang?",
                    "answer": "Aang is the protagonist...",
                    "sources": [
                        {"text": "...", "url": "...", "distance": 0.1},
                        ...
                    ],
                    "evidence": [  # Only if use_citations=True
                        {"cited_text": "...", "url": "...", ...}
                    ],
                    "usage": {
                        "total_tokens": 150,
                        "estimated_cost_usd": 0.002
                    }
                }
        """
        # Retrieve relevant chunks
        chunks = self.retriever.retrieve(
            query=query.strip(),
            k=k,
            metadata_filter=metadata_filter
        )

        # Generate answer (with or without citations)
        if use_citations:
            result = self.query_with_citations(query, k=k, metadata_filter=metadata_filter)
            answer = result["text"]
            evidence = result["evidence"]
        else:
            answer = self.query(query, k=k, metadata_filter=metadata_filter)
            evidence = None

        # Get usage stats from LLM client
        usage = self.llm_client.get_usage_stats()

        # Format sources
        sources = [
            {
                "text": chunk["text"],
                "url": chunk["metadata"].get("url", "Unknown"),
                "distance": chunk["distance"]
            }
            for chunk in chunks
        ]

        # Build response
        response = {
            "query": query,
            "answer": answer,
            "sources": sources,
            "usage": usage
        }

        # Add evidence if citations were used
        if use_citations and evidence is not None:
            response["evidence"] = evidence

        return response

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get LLM usage statistics.

        Returns:
            Dictionary with usage stats (tokens, cost, etc.)
        """
        return self.llm_client.get_usage_stats()

    def query_with_citations(
        self,
        query: str,
        k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024
    ) -> Dict[str, Any]:
        """
        Execute RAG query with automatic citation tracking.

        This method uses Claude's citation feature to track which chunks
        support each claim in the response, providing verifiable evidence.

        Args:
            query: User question
            k: Number of chunks to retrieve (default: 10)
            metadata_filter: Optional metadata filter
            temperature: Sampling temperature (default: 0.3 for factual)
            max_tokens: Maximum tokens to generate (default: 1024)

        Returns:
            Dictionary with structure:
                {
                    "text": "Generated answer",
                    "evidence": [
                        {
                            "cited_text": "Exact text from chunk",
                            "url": "wiki/page",
                            "title": "Page Title",
                            "document_index": 0,
                            "location": {"start": 0, "end": 27}
                        },
                        ...
                    ]
                }

        Raises:
            ValueError: If query is empty

        Example:
            >>> engine = QueryEngine("avatar_wiki")
            >>> result = engine.query_with_citations("Who is Aang?")
            >>> print(result["text"])
            >>> print(f"Citations: {len(result['evidence'])}")
        """
        # Validate query
        if not query or not query.strip():
            raise ValueError("query cannot be empty")

        # Retrieve relevant chunks
        chunks = self.retriever.retrieve(
            query=query.strip(),
            k=k,
            metadata_filter=metadata_filter
        )

        # If no chunks found, return empty result
        if not chunks:
            return {
                "text": "",
                "evidence": []
            }

        # Build documents and metadata for citation-enabled query
        documents = [chunk["text"] for chunk in chunks]
        document_metadata = [chunk["metadata"] for chunk in chunks]

        # Build query prompt
        prompt = f"""Based on the provided wiki content, please answer the following question.

Question: {query.strip()}

Please provide a clear, concise answer based only on the information in the documents."""

        # Query LLM with citations
        result = self.llm_client.query_with_citations(
            query=prompt,
            documents=documents,
            document_metadata=document_metadata,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return result
