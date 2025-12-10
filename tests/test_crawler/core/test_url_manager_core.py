"""
HIGH-QUALITY tests for URLManager core logic.

Tests queue management, deduplication, and priority logic.
Uses real temp files to test persistence.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.crawler.core.url_manager import URLManager


pytestmark = pytest.mark.unit


class TestURLQueueManagement:
    """Test URL queue operations and priority logic."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_add_url_returns_true_for_new_url(self, temp_project_dir):
        """Should return True when adding new URL."""
        manager = URLManager(temp_project_dir)

        result = manager.add_url("https://test.com/page1")

        assert result is True

    def test_add_url_adds_to_queue(self, temp_project_dir):
        """Should add URL to internal queue."""
        manager = URLManager(temp_project_dir)

        manager.add_url("https://test.com/page1")

        assert manager.queue_size() == 1

    def test_add_url_prevents_duplicates(self, temp_project_dir):
        """Should not add same URL twice."""
        manager = URLManager(temp_project_dir)

        result1 = manager.add_url("https://test.com/page1")
        result2 = manager.add_url("https://test.com/page1")

        assert result1 is True
        assert result2 is False
        assert manager.queue_size() == 1

    def test_add_url_does_not_add_visited_url(self, temp_project_dir):
        """Should not add URL that's already been visited."""
        manager = URLManager(temp_project_dir)

        url = "https://test.com/page1"
        manager.mark_visited(url)

        result = manager.add_url(url)

        assert result is False
        assert manager.queue_size() == 0

    def test_add_url_strips_whitespace(self, temp_project_dir):
        """Should strip whitespace from URLs."""
        manager = URLManager(temp_project_dir)

        manager.add_url("  https://test.com/page1  ")

        # Should be queryable without whitespace
        assert manager.is_queued("https://test.com/page1")

    def test_add_url_rejects_empty_string(self, temp_project_dir):
        """Should reject empty string URLs."""
        manager = URLManager(temp_project_dir)

        result = manager.add_url("")

        assert result is False
        assert manager.queue_size() == 0

    def test_add_url_rejects_whitespace_only(self, temp_project_dir):
        """Should reject whitespace-only URLs."""
        manager = URLManager(temp_project_dir)

        result = manager.add_url("   ")

        assert result is False
        assert manager.queue_size() == 0


class TestPriorityOrdering:
    """Test priority queue ordering logic - CRITICAL for crawl efficiency."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_get_next_url_returns_highest_priority(self, temp_project_dir):
        """Should return URL with highest priority first."""
        manager = URLManager(temp_project_dir)

        # Add URLs with different priorities
        manager.add_url("https://test.com/low", priority=1)
        manager.add_url("https://test.com/high", priority=10)
        manager.add_url("https://test.com/medium", priority=5)

        # Should get high priority first
        url = manager.get_next_url()
        assert url == "https://test.com/high"

        # Then medium
        url = manager.get_next_url()
        assert url == "https://test.com/medium"

        # Then low
        url = manager.get_next_url()
        assert url == "https://test.com/low"

    def test_get_next_url_removes_from_queue(self, temp_project_dir):
        """Should remove URL from queue when retrieved."""
        manager = URLManager(temp_project_dir)

        manager.add_url("https://test.com/page1")
        assert manager.queue_size() == 1

        url = manager.get_next_url()

        assert url == "https://test.com/page1"
        assert manager.queue_size() == 0

    def test_get_next_url_returns_none_when_empty(self, temp_project_dir):
        """Should return None when queue is empty."""
        manager = URLManager(temp_project_dir)

        url = manager.get_next_url()

        assert url is None

    def test_priority_zero_is_default(self, temp_project_dir):
        """URLs with no priority should default to 0."""
        manager = URLManager(temp_project_dir)

        manager.add_url("https://test.com/default")
        manager.add_url("https://test.com/explicit", priority=0)
        manager.add_url("https://test.com/high", priority=5)

        # High priority first
        assert manager.get_next_url() == "https://test.com/high"

        # Then default priority (order not guaranteed between same priority)
        next_urls = {manager.get_next_url(), manager.get_next_url()}
        assert "https://test.com/default" in next_urls
        assert "https://test.com/explicit" in next_urls


class TestBatchOperations:
    """Test batch URL addition."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_add_urls_adds_multiple(self, temp_project_dir):
        """Should add multiple URLs at once."""
        manager = URLManager(temp_project_dir)

        urls = [
            "https://test.com/page1",
            "https://test.com/page2",
            "https://test.com/page3"
        ]

        count = manager.add_urls(urls)

        assert count == 3
        assert manager.queue_size() == 3

    def test_add_urls_filters_duplicates(self, temp_project_dir):
        """Should filter out duplicate URLs in batch."""
        manager = URLManager(temp_project_dir)

        urls = [
            "https://test.com/page1",
            "https://test.com/page1",  # Duplicate
            "https://test.com/page2"
        ]

        count = manager.add_urls(urls)

        assert count == 2  # Only 2 unique
        assert manager.queue_size() == 2

    def test_add_urls_skips_already_visited(self, temp_project_dir):
        """Should not add URLs that are already visited."""
        manager = URLManager(temp_project_dir)

        manager.mark_visited("https://test.com/page1")

        urls = [
            "https://test.com/page1",  # Already visited
            "https://test.com/page2"
        ]

        count = manager.add_urls(urls)

        assert count == 1
        assert manager.queue_size() == 1

    def test_add_urls_returns_zero_for_empty_list(self, temp_project_dir):
        """Should handle empty URL list."""
        manager = URLManager(temp_project_dir)

        count = manager.add_urls([])

        assert count == 0


class TestVisitedTracking:
    """Test visited URL tracking logic."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_mark_visited_adds_to_visited_set(self, temp_project_dir):
        """Should add URL to visited set."""
        manager = URLManager(temp_project_dir)

        manager.mark_visited("https://test.com/page1")

        assert manager.is_visited("https://test.com/page1")
        assert manager.visited_count() == 1

    def test_mark_visited_strips_whitespace(self, temp_project_dir):
        """Should strip whitespace when marking visited."""
        manager = URLManager(temp_project_dir)

        manager.mark_visited("  https://test.com/page1  ")

        # Should be queryable without whitespace
        assert manager.is_visited("https://test.com/page1")

    def test_mark_visited_removes_from_failed(self, temp_project_dir):
        """Should remove URL from failed dict if marked as visited."""
        manager = URLManager(temp_project_dir)

        url = "https://test.com/page1"
        manager.mark_failed(url, "Error message")

        # Now mark as visited
        manager.mark_visited(url)

        # Should no longer be in internal failed dict
        # (get_statistics doesn't expose failed_urls, so we check internally)
        assert url not in manager._failed_dict

    def test_is_visited_returns_false_for_empty_string(self, temp_project_dir):
        """Should return False for empty string."""
        manager = URLManager(temp_project_dir)

        assert manager.is_visited("") is False

    def test_is_visited_returns_false_for_new_url(self, temp_project_dir):
        """Should return False for URL that hasn't been visited."""
        manager = URLManager(temp_project_dir)

        assert manager.is_visited("https://test.com/new") is False


class TestFailedURLTracking:
    """Test failed URL tracking."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_mark_failed_stores_error_message(self, temp_project_dir):
        """Should store error message for failed URL."""
        manager = URLManager(temp_project_dir)

        url = "https://test.com/failed"
        error = "404 Not Found"

        manager.mark_failed(url, error)

        # Check internal failed dict (not exposed in stats)
        assert url in manager._failed_dict
        assert manager._failed_dict[url] == error

    def test_mark_failed_handles_empty_error(self, temp_project_dir):
        """Should handle None or empty error message."""
        manager = URLManager(temp_project_dir)

        url = "https://test.com/failed"
        manager.mark_failed(url, "")

        # Check internal failed dict
        assert url in manager._failed_dict
        assert manager._failed_dict[url] == "Unknown error"


class TestStatePersistence:
    """Test saving and loading state - CRITICAL for resumable crawls."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_save_state_creates_files(self, temp_project_dir):
        """Should create state files when saving."""
        manager = URLManager(temp_project_dir)

        manager.add_url("https://test.com/page1")
        manager.mark_visited("https://test.com/visited")

        manager.save_state()

        assert manager.queue_file.exists()
        assert manager.visited_file.exists()

    def test_load_state_restores_queue(self, temp_project_dir):
        """Should restore queue from saved state."""
        # Create first manager and save state
        manager1 = URLManager(temp_project_dir)
        manager1.add_url("https://test.com/page1", priority=5)
        manager1.add_url("https://test.com/page2", priority=10)
        manager1.save_state()

        # Create new manager - should load state
        manager2 = URLManager(temp_project_dir)

        # Should have same queue
        assert manager2.queue_size() == 2

        # Should preserve priority ordering
        assert manager2.get_next_url() == "https://test.com/page2"  # Higher priority
        assert manager2.get_next_url() == "https://test.com/page1"

    def test_load_state_restores_visited(self, temp_project_dir):
        """Should restore visited set from saved state."""
        # Create first manager and save state
        manager1 = URLManager(temp_project_dir)
        manager1.mark_visited("https://test.com/visited1")
        manager1.mark_visited("https://test.com/visited2")
        manager1.save_state()

        # Create new manager - should load state
        manager2 = URLManager(temp_project_dir)

        # Should have same visited set
        assert manager2.visited_count() == 2
        assert manager2.is_visited("https://test.com/visited1")
        assert manager2.is_visited("https://test.com/visited2")

    def test_load_state_restores_failed_urls(self, temp_project_dir):
        """Should restore failed URLs from saved state."""
        # Create first manager and save state
        manager1 = URLManager(temp_project_dir)
        manager1.mark_failed("https://test.com/failed1", "Error 1")
        manager1.mark_failed("https://test.com/failed2", "Error 2")
        manager1.save_state()

        # Create new manager - should load state
        manager2 = URLManager(temp_project_dir)

        # Check internal failed dict
        assert len(manager2._failed_dict) == 2
        assert manager2._failed_dict["https://test.com/failed1"] == "Error 1"


class TestQueueMembership:
    """Test queue membership checking."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_is_queued_returns_true_for_queued_url(self, temp_project_dir):
        """Should return True for URL in queue."""
        manager = URLManager(temp_project_dir)

        manager.add_url("https://test.com/page1")

        assert manager.is_queued("https://test.com/page1") is True

    def test_is_queued_returns_false_after_popping(self, temp_project_dir):
        """Should return False after URL is popped from queue."""
        manager = URLManager(temp_project_dir)

        manager.add_url("https://test.com/page1")
        manager.get_next_url()

        assert manager.is_queued("https://test.com/page1") is False

    def test_is_queued_returns_false_for_new_url(self, temp_project_dir):
        """Should return False for URL not in queue."""
        manager = URLManager(temp_project_dir)

        assert manager.is_queued("https://test.com/new") is False
