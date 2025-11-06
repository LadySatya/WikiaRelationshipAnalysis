"""
ProfileBuilder tools package.

Provides modular, testable tools for LLM-driven profile building.

Architecture:
- ToolBase: Abstract base class for all tools
- ToolRegistry: Central registry for managing tools
- WikiSearchTool: Search wiki content with RAG
- RelationshipVerifyTool: Verify relationship claims
- CharacterContextTool: Get character background

Usage:
    >>> from src.processor.analysis.tools import ToolRegistry
    >>> from src.processor.rag.query_engine import QueryEngine
    >>>
    >>> query_engine = QueryEngine("avatar_wiki")
    >>> registry = ToolRegistry(query_engine)
    >>>
    >>> # Get tools for LLM
    >>> tools = registry.to_anthropic_format()
    >>>
    >>> # Execute tool
    >>> result = registry.execute("search_wiki", query="Aang")

Adding a new tool:
    1. Create tool file (e.g., tools/my_tool.py)
    2. Extend ToolBase and implement interface
    3. Register in ToolRegistry._register_default_tools()
    4. Export in this file
"""
from .base import ToolBase
from .registry import ToolRegistry
from .wiki_search_tool import WikiSearchTool
from .relationship_verify_tool import RelationshipVerifyTool
from .character_context_tool import CharacterContextTool

__all__ = [
    "ToolBase",
    "ToolRegistry",
    "WikiSearchTool",
    "RelationshipVerifyTool",
    "CharacterContextTool"
]

# Version info
__version__ = "1.0.0"
