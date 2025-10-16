"""
Configuration loader for RAG processor components.

Centralized config management - all components load config through this module.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import yaml


class ProcessorConfig:
    """
    Loads and provides access to processor configuration from YAML file.

    Singleton pattern ensures config is loaded only once.
    """

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config loader.

        Args:
            config_path: Path to config file (default: config/processor_config.yaml)
        """
        # Only load config once (singleton)
        if self._config is None:
            self._config = self._load_config(config_path)

    @staticmethod
    def _load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config file (default: config/processor_config.yaml)

        Returns:
            Configuration dictionary
        """
        if config_path is None:
            # Default to config/processor_config.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "processor_config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            # Return empty config if file doesn't exist (will use hardcoded defaults)
            return {}

        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get nested config value using dot notation.

        Args:
            *keys: Nested keys to traverse (e.g., "processor", "rag", "chunk_size")
            default: Default value if key not found

        Returns:
            Config value or default

        Example:
            >>> config = ProcessorConfig()
            >>> config.get("processor", "rag", "chunk_size")
            500
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value

    @property
    def embedding_provider(self) -> str:
        """Get default embedding provider."""
        return self.get("processor", "rag", "embedding_provider", default="local")

    @property
    def local_model(self) -> str:
        """Get local embedding model name."""
        return self.get("processor", "rag", "local_model", default="all-MiniLM-L6-v2")

    @property
    def voyage_model(self) -> str:
        """Get Voyage AI model name."""
        return self.get("processor", "rag", "voyage_model", default="voyage-3-lite")

    @property
    def chunk_size(self) -> int:
        """Get chunk size for text splitting."""
        return self.get("processor", "rag", "chunk_size", default=500)

    @property
    def chunk_overlap(self) -> int:
        """Get chunk overlap size."""
        return self.get("processor", "rag", "chunk_overlap", default=50)

    @property
    def vector_store_type(self) -> str:
        """Get vector store type."""
        return self.get("processor", "rag", "vector_store_type", default="chromadb")

    @property
    def vector_store_path(self) -> str:
        """Get vector store path."""
        return self.get("processor", "rag", "vector_store_path", default="data/vector_stores")

    @property
    def default_k(self) -> int:
        """Get default number of chunks to retrieve."""
        return self.get("processor", "rag", "default_k", default=10)

    @property
    def llm_provider(self) -> str:
        """Get LLM provider."""
        return self.get("processor", "rag", "llm_provider", default="anthropic")

    @property
    def llm_model(self) -> str:
        """Get LLM model name."""
        return self.get("processor", "rag", "llm_model", default="claude-3-5-haiku-20241022")


# Convenience function for quick access
def get_config() -> ProcessorConfig:
    """Get singleton instance of ProcessorConfig."""
    return ProcessorConfig()
