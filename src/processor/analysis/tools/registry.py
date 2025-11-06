"""
ToolRegistry - Manages available tools for ProfileBuilder.

Central registry that:
- Registers all available tools
- Provides tools in Anthropic API format
- Executes tool calls from LLM
- Makes it easy to add/remove tools
"""
from typing import Dict, List, Any
from .base import ToolBase
from .wiki_search_tool import WikiSearchTool
from .relationship_verify_tool import RelationshipVerifyTool
from .character_context_tool import CharacterContextTool


class ToolRegistry:
    """
    Registry of available tools for ProfileBuilder.

    This is the central hub for tool management. It:
    1. Registers tools (auto-registration of defaults)
    2. Provides tools to LLM (Anthropic API format)
    3. Executes tool calls (callback from LLM)
    4. Manages tool lifecycle (add/remove)

    Usage:
        >>> from .tools import ToolRegistry
        >>> registry = ToolRegistry(query_engine)
        >>>
        >>> # Get tools for LLM
        >>> tools = registry.to_anthropic_format()
        >>>
        >>> # Execute tool call from LLM
        >>> result = registry.execute("search_wiki", query="Aang relationships")
        >>>
        >>> # List available tools
        >>> print(registry.list_tools())
        ['search_wiki', 'verify_relationship', 'get_character_context']
    """

    def __init__(self, query_engine):
        """
        Initialize registry with QueryEngine dependency.

        Args:
            query_engine: QueryEngine instance (passed to tools)
        """
        self.query_engine = query_engine
        self._tools: Dict[str, ToolBase] = {}

        # Auto-register default tools
        self._register_default_tools()

    def _register_default_tools(self):
        """
        Register built-in tools.

        Default tools:
        - WikiSearchTool: Search wiki content
        - RelationshipVerifyTool: Verify relationships
        - CharacterContextTool: Get character background
        """
        self.register(WikiSearchTool(self.query_engine))
        self.register(RelationshipVerifyTool(self.query_engine))
        self.register(CharacterContextTool(self.query_engine))

    def register(self, tool: ToolBase):
        """
        Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool name conflicts with existing tool
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' already registered. "
                f"Use unregister() first or choose a different name."
            )

        self._tools[tool.name] = tool
        print(f"[INFO] Registered tool: {tool.name}")

    def unregister(self, name: str):
        """
        Remove a tool from registry.

        Args:
            name: Tool name to remove

        Raises:
            ValueError: If tool not found
        """
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not registered")

        del self._tools[name]
        print(f"[INFO] Unregistered tool: {name}")

    def get(self, name: str) -> ToolBase:
        """
        Get tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance

        Raises:
            ValueError: If tool not found
        """
        if name not in self._tools:
            raise ValueError(
                f"Unknown tool: '{name}'. "
                f"Available tools: {', '.join(self.list_tools())}"
            )
        return self._tools[name]

    def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool by name.

        This is the callback used by LLMClient when Claude makes tool calls.

        Args:
            name: Tool name (from LLM tool call)
            **kwargs: Tool parameters (from LLM tool call)

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            RuntimeError: If tool execution fails

        Example:
            >>> result = registry.execute(
            ...     "search_wiki",
            ...     query="Aang relationships",
            ...     max_results=10
            ... )
        """
        tool = self.get(name)

        try:
            return tool.execute(**kwargs)
        except Exception as e:
            # Re-raise with context
            raise RuntimeError(
                f"Tool '{name}' execution failed: {e}"
            ) from e

    def to_anthropic_format(self) -> List[Dict[str, Any]]:
        """
        Convert all tools to Anthropic API format.

        This is used by LLMClient to provide tools to Claude.

        Returns:
            List of tool definitions:
            [
                {
                    "name": "search_wiki",
                    "description": "...",
                    "input_schema": {...}
                },
                ...
            ]
        """
        return [
            tool.to_anthropic_format()
            for tool in self._tools.values()
        ]

    def list_tools(self) -> List[str]:
        """
        List available tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_tool_descriptions(self) -> str:
        """
        Get human-readable tool descriptions.

        Useful for debugging, documentation, and logging.

        Returns:
            Formatted string describing all tools
        """
        lines = ["Available Tools:", ""]

        for tool in self._tools.values():
            lines.append(f"- {tool.name}")

            # Get first line of description
            desc_first_line = tool.description.split("\n")[0]
            lines.append(f"  {desc_first_line}")
            lines.append("")

        return "\n".join(lines)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<ToolRegistry: {len(self._tools)} tools>"
