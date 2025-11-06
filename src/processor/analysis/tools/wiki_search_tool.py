"""
WikiSearchTool - Search wiki content with RAG.

Allows LLM to search for specific information in the wiki corpus.
This is the primary tool for gathering information about characters,
relationships, events, and other wiki content.
"""
from typing import Optional, Dict, Any
from .base import ToolBase


class WikiSearchTool(ToolBase):
    """
    Search wiki content using RAG semantic search.

    This tool combines:
    - Semantic search (finds relevant chunks)
    - LLM synthesis (generates coherent answer)
    - Citation tracking (tracks evidence)

    Use cases:
    - Discovering character relationships
    - Finding details about specific relationships
    - Learning background about characters
    - Verifying claims about events

    Query Caching:
    - Caches results to avoid redundant queries
    - Cache key: (query, character_url, max_results)
    - Cache persists for lifetime of tool instance (typically one build session)
    """

    def __init__(self, query_engine):
        """
        Initialize tool with QueryEngine dependency.

        Args:
            query_engine: QueryEngine instance for RAG queries
        """
        self.query_engine = query_engine
        self._cache: Dict[tuple, Dict[str, Any]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    @property
    def name(self) -> str:
        return "search_wiki"

    @property
    def description(self) -> str:
        return """Search the wiki content for specific information using semantic search.

This is your primary tool for gathering information from the wiki. It uses RAG (Retrieval Augmented Generation) to find relevant content and synthesize answers.

Use this tool to:
- Discover who a character has relationships with
- Find details about a specific relationship between two characters
- Learn background information about a character
- Verify claims about characters, events, or relationships
- Search for character abilities, affiliations, or attributes

The tool automatically:
- Searches semantically (understands meaning, not just keywords)
- Synthesizes coherent answers from multiple sources
- Tracks citations (which wiki pages support the answer)
- Ranks sources by relevance

When to use:
- To start investigating a character's relationships
- When you need details about a specific relationship
- To understand context about an unfamiliar character
- To gather evidence for relationship claims

Returns:
- answer: Synthesized answer from wiki content
- evidence_count: Number of citations supporting the answer
- top_sources: URLs of most relevant wiki pages
- citations: Sample citations with text excerpts"""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language search query. Be specific and clear. "
                        "Good examples: "
                        "'Who does Aang have relationships with?', "
                        "'How did Zuko and Aang become friends?', "
                        "'What is Katara and Aang relationship history?'. "
                        "Bad examples: "
                        "'Aang' (too vague), "
                        "'relationships' (needs character context)"
                    )
                },
                "character_url": {
                    "type": "string",
                    "description": (
                        "Optional: URL of a specific character's wiki page. "
                        "Use this to filter results to only that character's page. "
                        "Helpful when searching for info specific to one character "
                        "or when disambiguating characters with the same name."
                    )
                },
                "max_results": {
                    "type": "integer",
                    "description": (
                        "Maximum number of wiki chunks to retrieve. "
                        "Default: 10. "
                        "Use higher values (15-20) for comprehensive searches. "
                        "Use lower values (5-8) for quick lookups."
                    ),
                    "default": 10
                }
            },
            "required": ["query"]
        }

    def execute(
        self,
        query: str,
        character_url: Optional[str] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Execute wiki search with RAG.

        Checks cache first to avoid redundant queries. If not cached,
        performs RAG query and caches the result.

        Args:
            query: Search query (natural language)
            character_url: Optional URL filter for specific character
            max_results: Max chunks to retrieve (default: 10)

        Returns:
            {
                "answer": "Synthesized answer from wiki content",
                "evidence_count": 5,
                "top_sources": ["wiki/Page1", "wiki/Page2", ...],
                "citations": [
                    {"text": "Citation excerpt...", "url": "wiki/Page1"},
                    ...
                ],
                "cached": True/False  # Indicates if result was from cache
            }

        Raises:
            ValueError: If query is empty
        """
        # Validate query
        if not query or not query.strip():
            raise ValueError("query cannot be empty")

        # Build cache key (normalize query to lowercase for better hit rate)
        cache_key = (query.strip().lower(), character_url, max_results)

        # Check cache
        if cache_key in self._cache:
            self._cache_hits += 1
            cached_result = self._cache[cache_key].copy()
            cached_result["cached"] = True
            return cached_result

        # Cache miss - execute query
        self._cache_misses += 1

        # Build metadata filter if character URL provided
        metadata_filter = None
        if character_url:
            # Extract page identifier from URL
            # Example: "https://avatar.fandom.com/wiki/Aang" -> "Aang"
            url_id = character_url.split("/wiki/")[-1] if "/wiki/" in character_url else character_url
            metadata_filter = {"source_url": url_id}

        # Query with citations
        result = self.query_engine.query_with_citations(
            query=query.strip(),
            k=max_results,
            metadata_filter=metadata_filter
        )

        # Extract unique source URLs
        source_urls = list(set(
            e.get("url", "Unknown")
            for e in result.get("evidence", [])
        ))

        # Format citations for LLM
        citations = [
            {
                "text": e.get("cited_text", "")[:200],  # First 200 chars
                "url": e.get("url", "Unknown")
            }
            for e in result.get("evidence", [])[:5]  # Top 5 citations
        ]

        # Format response
        formatted_result = {
            "answer": result.get("text", ""),
            "evidence_count": len(result.get("evidence", [])),
            "top_sources": source_urls[:3],  # Top 3 unique sources
            "citations": citations,
            "cached": False
        }

        # Cache the result (store copy without 'cached' flag)
        cache_entry = formatted_result.copy()
        cache_entry.pop("cached", None)
        self._cache[cache_key] = cache_entry

        return formatted_result

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            {
                "cache_size": 10,          # Number of cached queries
                "cache_hits": 15,          # Number of cache hits
                "cache_misses": 25,        # Number of cache misses
                "hit_rate": 0.375          # Hit rate (hits / total requests)
            }
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate
        }

    def clear_cache(self) -> None:
        """Clear all cached query results."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
