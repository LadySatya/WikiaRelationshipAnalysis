"""
CharacterContextTool - Get background info about a character.

Retrieves general background information about a character to help
understand their role in relationships and the story.
"""
from typing import Optional, Dict, Any
from .base import ToolBase


class CharacterContextTool(ToolBase):
    """
    Get background context about a character.

    Use this tool when you encounter an unfamiliar character
    and need to understand who they are before documenting
    their relationships.
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
        return "get_character_context"

    @property
    def description(self) -> str:
        return """Get background information about a character.

Use this tool to learn about a character's identity, role, and background.

The tool provides:
- Who the character is
- Their role in the story
- General background and history
- Key attributes or affiliations

When to use:
- When you encounter an unfamiliar character mentioned in relationships
- To understand context for relationship dynamics
- To verify character identities (especially with duplicate names)
- To distinguish between similar character names

Returns:
- context: Background summary about the character
- sources: URLs of wiki pages with more info

Note: If you already know the character from previous searches, you don't need this tool."""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "character_name": {
                    "type": "string",
                    "description": "Name of character to get context for (e.g., 'Zuko')"
                },
                "disambiguation": {
                    "type": "string",
                    "description": (
                        "Optional: Disambiguation tag if multiple characters share this name. "
                        "Example: For 'Bumi (King of Omashu)' use disambiguation='King of Omashu'"
                    )
                }
            },
            "required": ["character_name"]
        }

    def execute(
        self,
        character_name: str,
        disambiguation: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get character background context.

        Args:
            character_name: Character to research
            disambiguation: Optional disambiguation tag

        Returns:
            {
                "context": "Background summary about the character",
                "sources": ["wiki/Page1", "wiki/Page2"]
            }

        Raises:
            ValueError: If character_name is empty
        """
        # Validate input
        if not character_name or not character_name.strip():
            raise ValueError("character_name cannot be empty")

        # Build query with disambiguation if provided
        query = f"Who is {character_name.strip()}"
        if disambiguation:
            query += f" ({disambiguation.strip()})"
        query += "? Provide background information."

        # Query for context
        result = self.query_engine.query_with_citations(
            query=query,
            k=8  # Moderate number of chunks
        )

        # Extract unique source URLs
        source_urls = list(set(
            e.get("url", "Unknown")
            for e in result.get("evidence", [])
        ))

        # Format response
        return {
            "context": result.get("text", ""),
            "sources": source_urls[:3]  # Top 3 sources
        }
