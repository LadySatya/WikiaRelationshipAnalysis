"""
Crawl state persistence for resuming interrupted crawls.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class CrawlState:
    """Manages crawl state persistence and recovery."""

    def __init__(self, project_path: Path):
        """Initialize crawl state manager with project path."""
        if not isinstance(project_path, Path):
            raise TypeError("project_path must be a Path object")

        self.project_path = project_path
        self.state_dir = project_path / "crawl_state"
        self.state_file = self.state_dir / "current_state.json"
        self.checkpoint_dir = self.state_dir / "checkpoints"

        # Ensure directories exist
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, state: Dict[str, Any]) -> None:
        """Save current crawl state to disk."""
        if state is None:
            state = {}

        # Add timestamp if not present
        if "timestamp" not in state:
            state["timestamp"] = datetime.now().isoformat()

        # Write to file
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load saved crawl state from disk."""
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def has_saved_state(self) -> bool:
        """Check if a saved state exists."""
        return self.state_file.exists()

    def clear_state(self) -> None:
        """Clear saved state files."""
        if self.state_file.exists():
            self.state_file.unlink()

    def create_checkpoint(self, state: Dict[str, Any]) -> str:
        """Create a timestamped checkpoint of current state."""
        if state is None:
            state = {}

        # Generate checkpoint ID from timestamp
        checkpoint_id = self._generate_checkpoint_id()

        # Add checkpoint metadata
        checkpoint_data = state.copy()
        checkpoint_data["checkpoint_id"] = checkpoint_id
        checkpoint_data["checkpoint_timestamp"] = datetime.now().isoformat()

        # Save checkpoint file
        checkpoint_file = self._get_checkpoint_path(checkpoint_id)
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

        return checkpoint_id

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List available checkpoints with metadata."""
        if not self.checkpoint_dir.exists():
            return []

        checkpoints = []

        # Find all checkpoint files
        for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract metadata
                checkpoint_info = {
                    "checkpoint_id": data.get(
                        "checkpoint_id", checkpoint_file.stem
                    ),
                    "timestamp": data.get("checkpoint_timestamp", ""),
                    "pages_crawled": data.get("pages_crawled", 0),
                    "file_path": str(checkpoint_file),
                }
                checkpoints.append(checkpoint_info)
            except (json.JSONDecodeError, FileNotFoundError):
                continue

        # Sort by timestamp (most recent first)
        checkpoints.sort(key=lambda x: x["timestamp"], reverse=True)

        return checkpoints

    def restore_from_checkpoint(
            self, checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        """Restore state from specific checkpoint."""
        if not checkpoint_id:
            return None

        checkpoint_file = self._get_checkpoint_path(checkpoint_id)

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def get_crawl_session_info(self) -> Optional[Dict[str, Any]]:
        """Get metadata about current/last crawl session."""
        return self.load_state()

    def update_statistics(self, stats: Dict[str, Any]) -> None:
        """Update crawl statistics in state."""
        if stats is None:
            return

        # Load current state
        current_state = self.load_state()
        if current_state is None:
            current_state = {}

        # Update with new statistics
        current_state.update(stats)

        # Save updated state
        self.save_state(current_state)

    def _get_state_file_path(self) -> Path:
        """Get path to main state file."""
        return self.state_file

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get path to specific checkpoint file."""
        return self.checkpoint_dir / f"checkpoint_{checkpoint_id}.json"

    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint identifier."""
        # Use timestamp-based ID
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
