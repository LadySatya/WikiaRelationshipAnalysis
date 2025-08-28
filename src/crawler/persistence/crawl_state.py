"""
Crawl state persistence for resuming interrupted crawls.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from datetime import datetime


class CrawlState:
    """Manages crawl state persistence and recovery."""
    
    def __init__(self, project_path: Path):
        """Initialize crawl state manager with project path."""
        pass
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """Save current crawl state to disk."""
        pass
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load saved crawl state from disk."""
        pass
    
    def has_saved_state(self) -> bool:
        """Check if a saved state exists."""
        pass
    
    def clear_state(self) -> None:
        """Clear saved state files."""
        pass
    
    def create_checkpoint(self, state: Dict[str, Any]) -> None:
        """Create a timestamped checkpoint of current state."""
        pass
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List available checkpoints with metadata."""
        pass
    
    def restore_from_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Restore state from specific checkpoint."""
        pass
    
    def get_crawl_session_info(self) -> Dict[str, Any]:
        """Get metadata about current/last crawl session."""
        pass
    
    def update_statistics(self, stats: Dict[str, Any]) -> None:
        """Update crawl statistics in state."""
        pass
    
    def _get_state_file_path(self) -> Path:
        """Get path to main state file."""
        pass
    
    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get path to specific checkpoint file."""
        pass
    
    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint identifier."""
        pass