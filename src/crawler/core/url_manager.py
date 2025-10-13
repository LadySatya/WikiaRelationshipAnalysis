"""
URL queue management with deduplication and prioritization.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class URLManager:
    """Manages URL queue with deduplication and persistence."""

    def __init__(self, project_path: Path):
        """Initialize URL manager with project storage path."""
        if not isinstance(project_path, Path):
            raise TypeError("project_path must be a Path object")

        self.project_path = project_path
        self.queue_file = project_path / "cache" / "url_queue.json"
        self.visited_file = project_path / "cache" / "visited_urls.json"
        self.failed_file = project_path / "cache" / "failed_urls.json"

        # In-memory data structures
        self._queue = []  # List of (priority, url) tuples, sorted by priority
        self._queued_set = set()  # Set for O(1) lookup
        self._visited_set = set()
        self._failed_dict = {}  # url -> error message

        # Create cache directory if it doesn't exist
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state if files exist
        self.load_state()

    def add_url(self, url: str, priority: int = 0) -> bool:
        """Add URL to queue if not already visited, returns True if added."""
        if not url or not isinstance(url, str):
            return False

        url = url.strip()
        if not url:
            return False

        # Don't add if already visited or already in queue
        if url in self._visited_set or url in self._queued_set:
            return False

        # Add to queue and tracking set
        self._queue.append((priority, url))
        self._queued_set.add(url)

        # Re-sort queue by priority (higher priority first)
        self._queue.sort(key=lambda x: x[0], reverse=True)

        return True

    def add_urls(self, urls: List[str], priority: int = 0) -> int:
        """Add multiple URLs, returns count of URLs actually added."""
        if not urls:
            return 0

        added_count = 0
        for url in urls:
            if self.add_url(url, priority):
                added_count += 1

        return added_count

    def get_next_url(self) -> Optional[str]:
        """Get next URL to crawl from queue."""
        if not self._queue:
            return None

        # Get highest priority URL
        priority, url = self._queue.pop(0)
        self._queued_set.discard(url)

        return url

    def mark_visited(self, url: str) -> None:
        """Mark URL as visited/completed."""
        if url:
            self._visited_set.add(url.strip())
            # Remove from failed dict if it was there
            self._failed_dict.pop(url.strip(), None)

    def mark_failed(self, url: str, error: str) -> None:
        """Mark URL as failed with error message."""
        if url:
            url = url.strip()
            self._failed_dict[url] = error or "Unknown error"

    def is_visited(self, url: str) -> bool:
        """Check if URL has been visited."""
        if not url:
            return False
        return url.strip() in self._visited_set

    def is_queued(self, url: str) -> bool:
        """Check if URL is in the queue."""
        if not url:
            return False
        return url.strip() in self._queued_set

    def queue_size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    def visited_count(self) -> int:
        """Get count of visited URLs."""
        return len(self._visited_set)

    def save_state(self) -> None:
        """Save queue and visited state to disk."""
        # Save queue
        queue_data = [
            {"url": url, "priority": priority} for priority, url in self._queue
        ]
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2)

        # Save visited URLs
        with open(self.visited_file, "w", encoding="utf-8") as f:
            json.dump(list(self._visited_set), f, indent=2)

        # Save failed URLs
        with open(self.failed_file, "w", encoding="utf-8") as f:
            json.dump(self._failed_dict, f, indent=2)

    def load_state(self) -> None:
        """Load queue and visited state from disk."""
        # Load queue if file exists
        if self.queue_file.exists():
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    queue_data = json.load(f)
                    for item in queue_data:
                        url = item["url"]
                        priority = item["priority"]
                        self._queue.append((priority, url))
                        self._queued_set.add(url)
                # Sort queue by priority (higher priority first)
                self._queue.sort(key=lambda x: x[0], reverse=True)
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                # Reset to empty queue if file is corrupted
                self._queue = []
                self._queued_set = set()

        # Load visited URLs if file exists
        if self.visited_file.exists():
            try:
                with open(self.visited_file, "r", encoding="utf-8") as f:
                    visited_list = json.load(f)
                    self._visited_set = set(visited_list)
            except (json.JSONDecodeError, FileNotFoundError):
                self._visited_set = set()

        # Load failed URLs if file exists
        if self.failed_file.exists():
            try:
                with open(self.failed_file, "r", encoding="utf-8") as f:
                    self._failed_dict = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self._failed_dict = {}

    def clear_queue(self) -> None:
        """Clear the entire queue (but keep visited set)."""
        self._queue = []
        self._queued_set = set()

    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "queue_size": len(self._queue),
            "visited_count": len(self._visited_set),
            "failed_count": len(self._failed_dict),
            "total_urls": len(self._queue)
            + len(self._visited_set)
            + len(self._failed_dict),
        }
