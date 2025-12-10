"""
HIGH-QUALITY tests for ContentSaver core logic.

Tests file operations, filename generation, and indexing logic.
Uses real temp files to ensure file operations actually work.
"""
import pytest
import json
import tempfile
import shutil
from pathlib import Path
from src.crawler.persistence.content_saver import ContentSaver


pytestmark = pytest.mark.unit


class TestFilenameGeneration:
    """Test filename generation logic - critical for file organization."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_generate_filename_uses_title_when_provided(self, temp_project_dir):
        """Should use cleaned title for filename when available."""
        saver = ContentSaver(temp_project_dir)

        filename = saver._generate_filename(
            url="https://avatar.fandom.com/wiki/Aang",
            title="Aang | Avatar Wiki | Fandom"
        )

        # Should clean title and use it
        assert filename.startswith("Aang")
        assert filename.endswith(".json")
        assert "|" not in filename  # Should strip wiki suffix

    def test_generate_filename_uses_hash_when_no_title(self, temp_project_dir):
        """Should use URL hash when title not provided."""
        saver = ContentSaver(temp_project_dir)

        filename = saver._generate_filename(
            url="https://avatar.fandom.com/wiki/Some_Page",
            title=None
        )

        # Should be a hex hash
        assert filename.endswith(".json")
        assert len(filename) > 10  # Hash should be reasonably long
        # Should not contain URL parts
        assert "avatar" not in filename.lower()
        assert "wiki" not in filename.lower()

    def test_clean_title_for_filename_removes_invalid_chars(self, temp_project_dir):
        """Should remove filesystem-invalid characters from title."""
        saver = ContentSaver(temp_project_dir)

        # Test with various invalid characters
        cleaned = saver._clean_title_for_filename('Title/With\\Invalid:Chars*?"|<>')

        # Should not contain any invalid chars
        assert "/" not in cleaned
        assert "\\" not in cleaned
        assert ":" not in cleaned
        assert "*" not in cleaned
        assert "?" not in cleaned
        assert '"' not in cleaned
        assert "|" not in cleaned
        assert "<" not in cleaned
        assert ">" not in cleaned

    def test_clean_title_for_filename_limits_length(self, temp_project_dir):
        """Should limit filename length to reasonable maximum."""
        saver = ContentSaver(temp_project_dir)

        # Create a very long title
        long_title = "A" * 300

        cleaned = saver._clean_title_for_filename(long_title)

        # Should be truncated (typically to 200 or 255 chars)
        assert len(cleaned) < 256


class TestPageSaving:
    """Test page saving with real file operations."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_save_page_content_creates_file(self, temp_project_dir):
        """Should create JSON file with page content."""
        saver = ContentSaver(temp_project_dir)

        url = "https://test.com/page"
        content = {
            "title": "Test Page",
            "text": "Page content"
        }

        file_path = saver.save_page_content(url, content)

        # File should exist
        assert file_path.exists()
        assert file_path.suffix == ".json"

        # File should contain our content
        with open(file_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["url"] == url
        assert saved_data["content"] == content
        assert "saved_at" in saved_data

    def test_save_page_content_updates_index(self, temp_project_dir):
        """Should update page index when saving content."""
        saver = ContentSaver(temp_project_dir)

        url = "https://test.com/page"
        content = {"title": "Test"}

        saver.save_page_content(url, content)

        # Index file should exist
        assert saver.page_index_file.exists()

        # Index should contain our page
        with open(saver.page_index_file, "r", encoding="utf-8") as f:
            index = json.load(f)

        assert url in index
        assert index[url]["url"] == url
        assert "file_path" in index[url]

    def test_save_page_content_validates_empty_url(self, temp_project_dir):
        """Should raise error for empty URL."""
        saver = ContentSaver(temp_project_dir)

        with pytest.raises(ValueError, match="URL and content cannot be empty"):
            saver.save_page_content("", {"title": "Test"})

    def test_save_page_content_validates_empty_content(self, temp_project_dir):
        """Should raise error for empty content."""
        saver = ContentSaver(temp_project_dir)

        with pytest.raises(ValueError, match="URL and content cannot be empty"):
            saver.save_page_content("https://test.com/page", {})


class TestPageIndexManagement:
    """Test page index update logic."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_update_page_index_creates_new_index(self, temp_project_dir):
        """Should create new index file if it doesn't exist."""
        saver = ContentSaver(temp_project_dir)

        page_info = {
            "url": "https://test.com/page1",
            "file_path": "processed/page1.json",
            "saved_at": "2025-01-01T00:00:00"
        }

        saver.update_page_index(page_info)

        assert saver.page_index_file.exists()

        with open(saver.page_index_file, "r", encoding="utf-8") as f:
            index = json.load(f)

        assert page_info["url"] in index

    def test_update_page_index_appends_to_existing(self, temp_project_dir):
        """Should append new entries to existing index."""
        saver = ContentSaver(temp_project_dir)

        # Add first page
        page1 = {
            "url": "https://test.com/page1",
            "file_path": "processed/page1.json",
            "saved_at": "2025-01-01T00:00:00"
        }
        saver.update_page_index(page1)

        # Add second page
        page2 = {
            "url": "https://test.com/page2",
            "file_path": "processed/page2.json",
            "saved_at": "2025-01-01T00:01:00"
        }
        saver.update_page_index(page2)

        # Both should be in index
        with open(saver.page_index_file, "r", encoding="utf-8") as f:
            index = json.load(f)

        assert len(index) == 2
        assert page1["url"] in index
        assert page2["url"] in index

    def test_update_page_index_overwrites_duplicate_url(self, temp_project_dir):
        """Should overwrite existing entry for same URL."""
        saver = ContentSaver(temp_project_dir)

        url = "https://test.com/page"

        # Add initial entry
        page1 = {
            "url": url,
            "file_path": "processed/page1.json",
            "saved_at": "2025-01-01T00:00:00"
        }
        saver.update_page_index(page1)

        # Update with new file path
        page2 = {
            "url": url,
            "file_path": "processed/page2.json",
            "saved_at": "2025-01-01T00:01:00"
        }
        saver.update_page_index(page2)

        # Should only have one entry with updated info
        with open(saver.page_index_file, "r", encoding="utf-8") as f:
            index = json.load(f)

        assert len(index) == 1
        assert index[url]["file_path"] == "processed/page2.json"


class TestCrawlLogManagement:
    """Test crawl log with rotation logic."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_save_crawl_log_entry_creates_new_log(self, temp_project_dir):
        """Should create new log file with first entry."""
        saver = ContentSaver(temp_project_dir)

        entry = {
            "url": "https://test.com/page",
            "status": "success"
        }

        saver.save_crawl_log_entry(entry)

        assert saver.crawl_log_file.exists()

        with open(saver.crawl_log_file, "r", encoding="utf-8") as f:
            log_entries = json.load(f)

        assert len(log_entries) == 1
        assert log_entries[0]["url"] == entry["url"]
        assert "timestamp" in log_entries[0]  # Should add timestamp

    def test_save_crawl_log_entry_appends_entries(self, temp_project_dir):
        """Should append new entries to existing log."""
        saver = ContentSaver(temp_project_dir)

        # Add multiple entries
        for i in range(5):
            entry = {
                "url": f"https://test.com/page{i}",
                "status": "success"
            }
            saver.save_crawl_log_entry(entry)

        with open(saver.crawl_log_file, "r", encoding="utf-8") as f:
            log_entries = json.load(f)

        assert len(log_entries) == 5

    def test_save_crawl_log_entry_rotates_after_1000(self, temp_project_dir):
        """Should keep only last 1000 entries to prevent unbounded growth."""
        saver = ContentSaver(temp_project_dir)

        # Manually create a log with 1000 entries
        initial_entries = [
            {"url": f"https://test.com/page{i}", "status": "success"}
            for i in range(1000)
        ]

        with open(saver.crawl_log_file, "w", encoding="utf-8") as f:
            json.dump(initial_entries, f)

        # Add one more entry
        new_entry = {
            "url": "https://test.com/new_page",
            "status": "success"
        }
        saver.save_crawl_log_entry(new_entry)

        # Should still be 1000 entries (oldest dropped)
        with open(saver.crawl_log_file, "r", encoding="utf-8") as f:
            log_entries = json.load(f)

        assert len(log_entries) == 1000

        # First entry should be page1 (page0 was dropped)
        assert log_entries[0]["url"] == "https://test.com/page1"

        # Last entry should be our new one
        assert log_entries[-1]["url"] == "https://test.com/new_page"


class TestContentRetrieval:
    """Test retrieving saved content."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_get_saved_content_retrieves_existing_page(self, temp_project_dir):
        """Should retrieve content for saved URL."""
        saver = ContentSaver(temp_project_dir)

        url = "https://test.com/page"
        content = {"title": "Test", "text": "Content"}

        saver.save_page_content(url, content)

        # Retrieve content
        retrieved = saver.get_saved_content(url)

        assert retrieved is not None
        # get_saved_content returns only the content dict (not the full saved_data)
        assert retrieved == content

    def test_get_saved_content_returns_none_for_missing_url(self, temp_project_dir):
        """Should return None for URL not in index."""
        saver = ContentSaver(temp_project_dir)

        retrieved = saver.get_saved_content("https://test.com/nonexistent")

        assert retrieved is None

    def test_content_exists_returns_true_for_saved_page(self, temp_project_dir):
        """Should return True for existing content."""
        saver = ContentSaver(temp_project_dir)

        url = "https://test.com/page"
        content = {"title": "Test"}

        saver.save_page_content(url, content)

        assert saver.content_exists(url) is True

    def test_content_exists_returns_false_for_missing_page(self, temp_project_dir):
        """Should return False for non-existent content."""
        saver = ContentSaver(temp_project_dir)

        assert saver.content_exists("https://test.com/nonexistent") is False
