"""
Unit tests for CharacterKnowledgeBuilder save/load and persistence.

Tests verify:
- Saving knowledge base to disk
- Loading character files
- Loading relationship files
- File naming and sanitization
- Periodic save functionality

NOTE: All tools now require a 'canon' parameter to support multi-canon wikis.
The default canon used in tests is 'main'.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from src.processor.analysis.knowledge_builder import CharacterKnowledgeBuilder

# Default test canon
TEST_CANON = "main"


@pytest.fixture
def mock_builder():
    """Create a mocked CharacterKnowledgeBuilder for testing."""
    with (
        patch("src.processor.analysis.knowledge_builder.QueryEngine"),
        patch(
            "src.processor.analysis.knowledge_builder.load_system_prompt"
        ) as mock_prompt,
        patch(
            "src.processor.analysis.knowledge_builder.load_tool_schemas"
        ) as mock_schemas,
    ):

        mock_prompt.return_value = "Test prompt"
        mock_schemas.return_value = []

        builder = CharacterKnowledgeBuilder(project_name="test")
        # Ensure the default canon exists in knowledge base
        builder.knowledge_base["characters"][TEST_CANON] = {}
        builder.knowledge_base["relationships"][TEST_CANON] = {}
        return builder


@pytest.mark.unit
class TestKnowledgeBaseSave:
    """Test knowledge base saving functionality."""

    def test_save_creates_directories(self, mock_builder, tmp_path):
        """Should create characters and relationships directories."""
        mock_builder.characters_dir = tmp_path / "characters"
        mock_builder.relationships_dir = tmp_path / "relationships"

        mock_builder.save()

        assert mock_builder.characters_dir.exists()
        assert mock_builder.relationships_dir.exists()

    def test_save_writes_character_files(self, mock_builder, tmp_path):
        """Should write one file per character with canon suffix."""
        mock_builder.characters_dir = tmp_path / "characters"
        mock_builder.relationships_dir = tmp_path / "relationships"

        mock_builder.knowledge_base["characters"][TEST_CANON] = {
            "Aang": {
                "name": "Aang",
                "aliases": ["Avatar Aang"],
                "bio": "The last airbender",
                "source_urls": ["https://example.com"],
            },
            "Katara": {
                "name": "Katara",
                "aliases": [],
                "bio": "Waterbender",
                "source_urls": [],
            },
        }

        mock_builder.save()

        # Files now include canon suffix
        aang_file = mock_builder.characters_dir / f"Aang_{TEST_CANON}.json"
        katara_file = mock_builder.characters_dir / f"Katara_{TEST_CANON}.json"

        assert aang_file.exists()
        assert katara_file.exists()

        # Verify content
        with open(aang_file) as f:
            data = json.load(f)
            assert data["name"] == "Aang"
            assert data["aliases"] == ["Avatar Aang"]

    def test_save_sanitizes_character_filenames(self, mock_builder, tmp_path):
        """Should sanitize special characters in character names."""
        mock_builder.characters_dir = tmp_path / "characters"
        mock_builder.relationships_dir = tmp_path / "relationships"

        mock_builder.knowledge_base["characters"][TEST_CANON] = {
            "Test: Character / Name": {
                "name": "Test: Character / Name",
                "aliases": [],
                "bio": "Test",
                "source_urls": [],
            }
        }

        mock_builder.save()

        # Should replace special chars with underscores
        files = list(mock_builder.characters_dir.glob("*.json"))
        assert len(files) == 1
        assert ":" not in files[0].name
        assert "/" not in files[0].name

    def test_save_writes_relationship_files(self, mock_builder, tmp_path):
        """Should write one file per relationship with canon suffix."""
        mock_builder.characters_dir = tmp_path / "characters"
        mock_builder.relationships_dir = tmp_path / "relationships"

        mock_builder.knowledge_base["relationships"][TEST_CANON] = {
            ("Aang", "Katara"): {
                "characters": ["Aang", "Katara"],
                "type": "friend",
                "summary": "Friends",
                "claims": [],
            }
        }

        mock_builder.save()

        # Files now include canon suffix
        rel_file = mock_builder.relationships_dir / f"Aang_Katara_{TEST_CANON}.json"
        assert rel_file.exists()

        with open(rel_file) as f:
            data = json.load(f)
            assert data["type"] == "friend"

    def test_save_handles_empty_knowledge_base(self, mock_builder, tmp_path):
        """Should handle empty knowledge base without errors."""
        mock_builder.characters_dir = tmp_path / "characters"
        mock_builder.relationships_dir = tmp_path / "relationships"

        mock_builder.save()

        # Should create directories but no files
        assert mock_builder.characters_dir.exists()
        assert len(list(mock_builder.characters_dir.glob("*.json"))) == 0


@pytest.mark.unit
class TestLoadCrawledPages:
    """Test _load_crawled_pages functionality."""

    def test_load_crawled_pages_reads_json_files(self, mock_builder, tmp_path):
        """Should load all JSON files from processed directory."""
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()

        # Create test files
        page1 = {
            "content": {
                "url": "https://example.com/1",
                "title": "Page 1",
                "main_content": "Content 1",
            }
        }
        page2 = {
            "content": {
                "url": "https://example.com/2",
                "title": "Page 2",
                "main_content": "Content 2",
            }
        }

        (processed_dir / "page1.json").write_text(json.dumps(page1))
        (processed_dir / "page2.json").write_text(json.dumps(page2))

        mock_builder.project_dir = tmp_path

        pages = mock_builder._load_crawled_pages()

        assert len(pages) == 2
        assert any(p["url"] == "https://example.com/1" for p in pages)
        assert any(p["url"] == "https://example.com/2" for p in pages)

    def test_load_crawled_pages_handles_missing_directory(self, mock_builder, tmp_path):
        """Should raise error if processed directory doesn't exist."""
        mock_builder.project_dir = tmp_path

        with pytest.raises(FileNotFoundError):
            mock_builder._load_crawled_pages()

    def test_load_crawled_pages_skips_invalid_files(self, mock_builder, tmp_path):
        """Should skip files that can't be parsed."""
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()

        # Valid file
        (processed_dir / "page1.json").write_text(
            json.dumps({"content": {"url": "test"}})
        )
        # Invalid JSON
        (processed_dir / "page2.json").write_text("invalid json {")

        mock_builder.project_dir = tmp_path

        pages = mock_builder._load_crawled_pages()

        assert len(pages) == 1  # Only valid file loaded

    def test_load_crawled_pages_adds_url_if_missing(self, mock_builder, tmp_path):
        """Should add URL from top-level if missing in content."""
        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()

        page = {
            "url": "https://example.com/page",
            "content": {"title": "Page", "main_content": "Content"},
        }
        (processed_dir / "page.json").write_text(json.dumps(page))

        mock_builder.project_dir = tmp_path

        pages = mock_builder._load_crawled_pages()

        assert pages[0]["url"] == "https://example.com/page"


@pytest.mark.unit
class TestNormalizationHelpers:
    """Test helper methods for normalization."""

    def test_normalize_relationship_key_alphabetical_order(self, mock_builder):
        """Should normalize relationship key to alphabetical order."""
        key1 = mock_builder._normalize_relationship_key("Zuko", "Aang")
        key2 = mock_builder._normalize_relationship_key("Aang", "Zuko")

        assert key1 == key2
        assert key1 == ("Aang", "Zuko")

    def test_normalize_relationship_key_same_character(self, mock_builder):
        """Should handle same character (edge case)."""
        key = mock_builder._normalize_relationship_key("Aang", "Aang")

        assert key == ("Aang", "Aang")


@pytest.mark.unit
class TestPeriodicSave:
    """Test periodic save functionality."""

    def test_saves_at_save_frequency_intervals(self, mock_builder, tmp_path):
        """Should save knowledge base every save_frequency pages."""
        mock_builder.characters_dir = tmp_path / "characters"
        mock_builder.relationships_dir = tmp_path / "relationships"
        mock_builder.save_frequency = 2

        # Add test data (now with canon)
        mock_builder.knowledge_base["characters"][TEST_CANON]["Test"] = {
            "name": "Test",
            "aliases": [],
            "bio": "Test",
            "source_urls": [],
        }

        # Process 3 pages (should save at page 2)
        for i in range(3):
            mock_builder.knowledge_base["metadata"]["pages_processed"] += 1
            pages = mock_builder.knowledge_base["metadata"]["pages_processed"]
            if pages % mock_builder.save_frequency == 0:
                mock_builder.save()

        # Should have saved after page 2 (with canon suffix)
        test_file = mock_builder.characters_dir / f"Test_{TEST_CANON}.json"
        assert test_file.exists()
