"""
RelationshipVerifyTool - Verify relationship claims.

Checks if a relationship between two characters exists and measures
how strongly it's supported by wiki evidence.
"""
from typing import Dict, Any
import logging

from .base import ToolBase
from src.utils.logging_config import get_logger

logger = get_logger("llm")


class RelationshipVerifyTool(ToolBase):
    """
    Verify if two characters have a documented relationship.

    Use this tool to:
    - Double-check suspected relationships
    - Measure evidence strength
    - Get confidence scores for claims
    - Prioritize relationships by importance
    """

    def __init__(self, query_engine):
        """
        Initialize tool with QueryEngine dependency.

        Args:
            query_engine: QueryEngine instance for RAG queries
        """
        self.query_engine = query_engine

    @property
    def name(self) -> str:
        return "verify_relationship"

    @property
    def description(self) -> str:
        return """Verify if a relationship exists between two characters and measure evidence strength.

Use this tool to validate and measure the strength of relationship claims.

The tool:
- Searches for evidence of the relationship in wiki content
- Counts how many sources mention the relationship
- Calculates a confidence score (0.0-1.0)
- Provides a brief summary of the relationship

When to use:
- After finding a potential relationship via search_wiki
- To validate important relationships before including in profile
- To prioritize relationships by evidence strength (focus on high-confidence ones)
- To filter out weak or speculative relationships

Returns:
- relationship_exists: true if evidence found, false otherwise
- confidence: 0.0-1.0 score (0.8+ = strong, 0.5-0.8 = moderate, <0.5 = weak)
- evidence_count: Number of citations supporting the relationship
- summary: Brief description of the relationship

Confidence scoring:
- 5+ citations = 1.0 (very strong evidence)
- 3-4 citations = 0.6-0.8 (moderate evidence)
- 1-2 citations = 0.2-0.4 (weak evidence)
- 0 citations = 0.0 (no evidence)"""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "character_a": {
                    "type": "string",
                    "description": "First character's name (e.g., 'Aang')"
                },
                "character_b": {
                    "type": "string",
                    "description": "Second character's name (e.g., 'Katara')"
                }
            },
            "required": ["character_a", "character_b"]
        }

    def execute(
        self,
        character_a: str,
        character_b: str
    ) -> Dict[str, Any]:
        """
        Verify relationship between two characters.

        Args:
            character_a: First character name
            character_b: Second character name

        Returns:
            {
                "relationship_exists": true/false,
                "confidence": 0.0-1.0,
                "evidence_count": N,
                "summary": "Brief relationship description",
                "evidence": [{"cited_text": "...", "source_url": "...", ...}, ...]
            }

        Raises:
            ValueError: If character names are empty
        """
        # Validate inputs
        if not character_a or not character_a.strip():
            raise ValueError("character_a cannot be empty")
        if not character_b or not character_b.strip():
            raise ValueError("character_b cannot be empty")

        # Query for relationship
        query = f"What is the relationship between {character_a.strip()} and {character_b.strip()}?"

        # Retrieve relevant chunks directly (don't rely on Claude citations)
        chunks = self.query_engine.retriever.retrieve(
            query=query,
            k=15  # More chunks for better verification
        )

        # Query LLM for summary (with citations if available)
        llm_result = self.query_engine.query_with_citations(
            query=query,
            k=15
        )

        # Build evidence from retrieved chunks (guaranteed to have data)
        evidence = []
        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            evidence_entry = {
                "cited_text": chunk["text"][:300],  # First 300 chars of chunk
                "source_url": metadata.get("url", ""),  # Metadata uses "url" not "source_url"
                "page_title": metadata.get("title", ""),  # Metadata uses "title" not "page_title"
                "chunk_index": metadata.get("chunk_index", i),
                "namespace": metadata.get("namespace", ""),
                "relevance_score": chunk.get("distance", 0.0)  # Lower is better
            }
            evidence.append(evidence_entry)

        # Calculate confidence based on number of relevant chunks found
        evidence_count = len(evidence)
        confidence = min(1.0, evidence_count / 5.0)  # 5+ chunks = 1.0

        # Format response with full evidence
        return {
            "relationship_exists": evidence_count > 0,
            "confidence": round(confidence, 2),
            "evidence_count": evidence_count,
            "summary": llm_result.get("text", "")[:250],  # Brief summary (250 chars)
            "evidence": evidence  # Full evidence from retrieved chunks
        }
