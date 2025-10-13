"""
Tests for CrawlState class.
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.crawler.persistence.crawl_state import CrawlState

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


class TestCrawlStateInit:
    """Test CrawlState initialization."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_init_with_valid_project_path(self, temp_project_dir):
        """Test initialization with valid project path."""
        crawl_state = CrawlState(temp_project_dir)

        assert crawl_state.project_path == temp_project_dir
        assert hasattr(crawl_state, "state_file")
        assert hasattr(crawl_state, "checkpoint_dir")

    def test_init_creates_state_directory(self, temp_project_dir):
        """Test that initialization creates crawl_state directory."""
        crawl_state = CrawlState(temp_project_dir)

        state_dir = temp_project_dir / "crawl_state"
        assert state_dir.exists()
        assert state_dir.is_dir()

    def test_init_with_invalid_project_path(self):
        """Test initialization with invalid project path."""
        with pytest.raises(TypeError):
            CrawlState("not_a_path_object")

        with pytest.raises(TypeError):
            CrawlState(None)


class TestCrawlStateSaving:
    """Test CrawlState state saving functionality."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def crawl_state(self, temp_project_dir):
        """Create CrawlState instance for testing."""
        return CrawlState(temp_project_dir)

    @pytest.fixture
    def sample_state_data(self):
        """Sample crawl state data for testing."""
        return {
            "session_id": "test_session_123",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "pages_crawled": 45,
            "pages_attempted": 50,
            "errors": 3,
            "statistics": {"characters_found": 25, "total_links_discovered": 342},
        }

    def test_save_state_creates_file(self, crawl_state, sample_state_data):
        """Test that saving state creates state file."""
        crawl_state.save_state(sample_state_data)

        assert crawl_state.state_file.exists()

    def test_save_state_stores_data_correctly(self, crawl_state, sample_state_data):
        """Test that saved state contains correct data."""
        crawl_state.save_state(sample_state_data)

        # Read the file directly
        with open(crawl_state.state_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["session_id"] == sample_state_data["session_id"]
        assert saved_data["pages_crawled"] == sample_state_data["pages_crawled"]
        assert saved_data["statistics"]["characters_found"] == 25

    def test_save_state_adds_timestamp(self, crawl_state, sample_state_data):
        """Test that saving adds timestamp if not present."""
        # Don't include timestamp in input data
        state_without_timestamp = sample_state_data.copy()
        state_without_timestamp.pop("timestamp", None)

        crawl_state.save_state(state_without_timestamp)

        # Load and verify timestamp was added
        with open(crawl_state.state_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert "timestamp" in saved_data

    def test_save_state_overwrites_previous(self, crawl_state, sample_state_data):
        """Test that saving state overwrites previous state."""
        # Save first state
        crawl_state.save_state(sample_state_data)

        # Save updated state
        updated_state = sample_state_data.copy()
        updated_state["pages_crawled"] = 100
        crawl_state.save_state(updated_state)

        # Load and verify it's the updated version
        with open(crawl_state.state_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["pages_crawled"] == 100

    def test_save_empty_state(self, crawl_state):
        """Test saving empty state dictionary."""
        crawl_state.save_state({})

        assert crawl_state.state_file.exists()

        with open(crawl_state.state_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        # Should at least have timestamp
        assert "timestamp" in saved_data


class TestCrawlStateLoading:
    """Test CrawlState state loading functionality."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def crawl_state(self, temp_project_dir):
        """Create CrawlState instance for testing."""
        return CrawlState(temp_project_dir)

    def test_load_existing_state(self, crawl_state):
        """Test loading existing crawl state."""
        # Save a state first
        test_state = {"session_id": "test123", "pages_crawled": 50}
        crawl_state.save_state(test_state)

        # Load it back
        loaded_state = crawl_state.load_state()

        assert loaded_state is not None
        assert loaded_state["session_id"] == "test123"
        assert loaded_state["pages_crawled"] == 50

    def test_load_state_no_file_exists(self, crawl_state):
        """Test loading when no state file exists."""
        loaded_state = crawl_state.load_state()

        assert loaded_state is None

    def test_load_corrupted_state_file(self, crawl_state):
        """Test handling corrupted state file."""
        # Create corrupted file
        crawl_state.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(crawl_state.state_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json content }")

        loaded_state = crawl_state.load_state()

        # Should return None for corrupted file
        assert loaded_state is None

    def test_has_saved_state_true(self, crawl_state):
        """Test has_saved_state returns True when state exists."""
        crawl_state.save_state({"test": "data"})

        assert crawl_state.has_saved_state() is True

    def test_has_saved_state_false(self, crawl_state):
        """Test has_saved_state returns False when no state exists."""
        assert crawl_state.has_saved_state() is False


class TestCrawlStateCheckpointing:
    """Test CrawlState checkpointing functionality."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def crawl_state(self, temp_project_dir):
        """Create CrawlState instance for testing."""
        return CrawlState(temp_project_dir)

    def test_create_checkpoint(self, crawl_state):
        """Test creating state checkpoint."""
        test_state = {"pages_crawled": 100, "session_id": "test"}

        checkpoint_id = crawl_state.create_checkpoint(test_state)

        assert checkpoint_id is not None
        assert isinstance(checkpoint_id, str)
        assert len(checkpoint_id) > 0

    def test_checkpoint_creates_file(self, crawl_state):
        """Test that checkpoint creates a file."""
        test_state = {"pages_crawled": 100}

        checkpoint_id = crawl_state.create_checkpoint(test_state)

        # Verify checkpoint file exists
        checkpoint_files = list(crawl_state.checkpoint_dir.glob("*.json"))
        assert len(checkpoint_files) > 0

    def test_list_checkpoints_empty(self, crawl_state):
        """Test listing checkpoints when none exist."""
        checkpoints = crawl_state.list_checkpoints()

        assert isinstance(checkpoints, list)
        assert len(checkpoints) == 0

    def test_list_checkpoints_with_data(self, crawl_state):
        """Test listing checkpoints after creating some."""
        # Create multiple checkpoints
        crawl_state.create_checkpoint({"pages": 10})
        crawl_state.create_checkpoint({"pages": 20})
        crawl_state.create_checkpoint({"pages": 30})

        checkpoints = crawl_state.list_checkpoints()

        assert len(checkpoints) == 3
        # Should be sorted by timestamp (most recent first)
        assert isinstance(checkpoints[0], dict)
        assert "checkpoint_id" in checkpoints[0]
        assert "timestamp" in checkpoints[0]

    def test_restore_from_checkpoint(self, crawl_state):
        """Test restoring state from checkpoint."""
        test_state = {"pages_crawled": 75, "session_id": "checkpoint_test"}

        checkpoint_id = crawl_state.create_checkpoint(test_state)

        # Restore from checkpoint
        restored_state = crawl_state.restore_from_checkpoint(checkpoint_id)

        assert restored_state is not None
        assert restored_state["pages_crawled"] == 75
        assert restored_state["session_id"] == "checkpoint_test"

    def test_restore_from_nonexistent_checkpoint(self, crawl_state):
        """Test restoring from checkpoint that doesn't exist."""
        restored_state = crawl_state.restore_from_checkpoint("nonexistent_id")

        assert restored_state is None


class TestCrawlStateStatistics:
    """Test CrawlState statistics management."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def crawl_state(self, temp_project_dir):
        """Create CrawlState instance for testing."""
        return CrawlState(temp_project_dir)

    def test_update_statistics(self, crawl_state):
        """Test updating crawl statistics."""
        # Save initial state
        initial_state = {
            "session_id": "stats_test",
            "pages_crawled": 10,
            "statistics": {"characters_found": 5},
        }
        crawl_state.save_state(initial_state)

        # Update statistics
        new_stats = {"pages_crawled": 20, "statistics": {"characters_found": 15}}
        crawl_state.update_statistics(new_stats)

        # Load and verify update
        loaded_state = crawl_state.load_state()
        assert loaded_state["pages_crawled"] == 20
        assert loaded_state["statistics"]["characters_found"] == 15

    def test_get_crawl_session_info(self, crawl_state):
        """Test getting crawl session metadata."""
        # Save state with session info
        state = {
            "session_id": "session123",
            "start_time": "2024-01-15T10:00:00Z",
            "pages_crawled": 50,
        }
        crawl_state.save_state(state)

        session_info = crawl_state.get_crawl_session_info()

        assert session_info is not None
        assert "session_id" in session_info
        assert session_info["session_id"] == "session123"

    def test_get_crawl_session_info_no_state(self, crawl_state):
        """Test getting session info when no state exists."""
        session_info = crawl_state.get_crawl_session_info()

        # Should return empty dict or None
        assert session_info is None or session_info == {}


class TestCrawlStateCleanup:
    """Test CrawlState cleanup functionality."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def crawl_state(self, temp_project_dir):
        """Create CrawlState instance for testing."""
        return CrawlState(temp_project_dir)

    def test_clear_state(self, crawl_state):
        """Test clearing saved state."""
        # Save a state
        crawl_state.save_state({"test": "data"})
        assert crawl_state.has_saved_state() is True

        # Clear it
        crawl_state.clear_state()

        # Verify it's gone
        assert crawl_state.has_saved_state() is False

    def test_clear_state_when_none_exists(self, crawl_state):
        """Test clearing state when none exists (should not error)."""
        # Should not raise exception
        crawl_state.clear_state()

        assert crawl_state.has_saved_state() is False

    def test_clear_state_removes_file(self, crawl_state):
        """Test that clear_state removes the state file."""
        crawl_state.save_state({"test": "data"})
        assert crawl_state.state_file.exists()

        crawl_state.clear_state()

        assert not crawl_state.state_file.exists()
