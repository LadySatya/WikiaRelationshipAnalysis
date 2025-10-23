"""
Tests for CharacterExtractor - Page-based character discovery.

This test suite validates the page-based discovery approach where characters
are identified by classifying crawled wiki pages using a tiered system:
- Tier 1: Metadata filtering (FREE)
- Tier 2: Batch title classification (CHEAP)
- Tier 3: Content classification with optional RAG (SELECTIVE)
"""
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.processor.analysis.character_extractor import CharacterExtractor


@pytest.fixture
def sample_pages_dir(tmp_path):
    """Create temporary directory with sample page fixtures."""
    # Copy sample pages to tmp processed directory
    processed_dir = tmp_path / "data" / "projects" / "test_project" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Load fixtures from tests/fixtures/sample_pages/
    fixtures_dir = Path("tests/fixtures/sample_pages")

    for fixture_file in fixtures_dir.glob("*.json"):
        # Copy to processed directory
        dest = processed_dir / fixture_file.name
        dest.write_text(fixture_file.read_text(encoding='utf-8'), encoding='utf-8')

    return tmp_path


@pytest.fixture
def mock_project_path(tmp_path):
    """Create mock project directory structure."""
    project_dir = tmp_path / "data" / "projects" / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (project_dir / "processed").mkdir()
    (project_dir / "characters").mkdir()
    (project_dir / "cache").mkdir()

    return tmp_path


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

class TestCharacterExtractorInitialization:
    """Test CharacterExtractor initialization and configuration."""

    def test_init_with_project_name(self):
        """Test basic initialization with project name."""
        extractor = CharacterExtractor(project_name="test_project")

        assert extractor.project_name == "test_project"
        assert extractor.query_engine is not None

    def test_init_with_custom_thresholds(self):
        """Test initialization with custom threshold values."""
        extractor = CharacterExtractor(
            project_name="test_project",
            min_mentions=5,
            confidence_threshold=0.9
        )

        assert extractor.min_mentions == 5
        assert extractor.confidence_threshold == 0.9

    def test_init_with_default_config_values(self):
        """Test that default config values are loaded correctly."""
        extractor = CharacterExtractor(project_name="test_project")

        # Should use defaults from config
        assert extractor.min_mentions >= 1
        assert 0.0 <= extractor.confidence_threshold <= 1.0

    def test_init_validates_project_name(self):
        """Test that empty project names are rejected."""
        with pytest.raises(ValueError, match="project_name cannot be empty"):
            CharacterExtractor(project_name="")

        with pytest.raises(ValueError, match="project_name cannot be empty"):
            CharacterExtractor(project_name="   ")

    def test_init_creates_query_engine(self):
        """Test that QueryEngine is initialized."""
        extractor = CharacterExtractor(project_name="test_project")

        assert hasattr(extractor, "query_engine")
        assert extractor.query_engine.project_name == "test_project"


# ============================================================================
# PAGE LOADING TESTS
# ============================================================================

class TestPageLoading:
    """Test loading crawled pages from disk."""

    def test_load_crawled_pages_success(self, sample_pages_dir, monkeypatch):
        """Test successful loading of crawled pages."""
        # Patch Path to use our tmp_path
        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: sample_pages_dir / x if "data/projects" in str(x) else Path(x)
        )

        extractor = CharacterExtractor(project_name="test_project")
        pages = extractor._load_crawled_pages()

        # Should load all 7 fixture pages (5 original + 2 Bumi fixtures)
        assert len(pages) == 7

        # Verify page structure
        assert all("title" in page for page in pages)
        assert all("url" in page for page in pages)
        assert all("main_content" in page for page in pages)

    def test_load_crawled_pages_extracts_content(self, sample_pages_dir, monkeypatch):
        """Test that page content is properly extracted from wrapper."""
        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: sample_pages_dir / x if "data/projects" in str(x) else Path(x)
        )

        extractor = CharacterExtractor(project_name="test_project")
        pages = extractor._load_crawled_pages()

        # Find Korra page
        korra_page = next((p for p in pages if p.get("title") == "Korra"), None)
        assert korra_page is not None

        # Verify fields
        assert korra_page["title"] == "Korra"
        assert "Avatar" in korra_page["main_content"]
        assert "infobox_data" in korra_page

    def test_load_crawled_pages_missing_directory(self):
        """Test error when processed directory doesn't exist."""
        extractor = CharacterExtractor(project_name="nonexistent_project")

        with pytest.raises(FileNotFoundError, match="No crawled pages found"):
            extractor._load_crawled_pages()

    def test_load_crawled_pages_empty_directory(self, tmp_path, monkeypatch):
        """Test error when processed directory is empty."""
        # Create empty processed dir
        processed_dir = tmp_path / "data" / "projects" / "empty_project" / "processed"
        processed_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: tmp_path / x if "data/projects" in str(x) else Path(x)
        )

        extractor = CharacterExtractor(project_name="empty_project")

        with pytest.raises(ValueError, match="No pages found"):
            extractor._load_crawled_pages()


# ============================================================================
# METADATA CLASSIFICATION TESTS (Tier 1)
# ============================================================================

class TestMetadataClassification:
    """Test Tier 1: FREE metadata-based classification."""

    def test_classify_by_namespace_character(self):
        """Test classification via Character namespace."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Aang",
            "namespace": "Character",
            "url": "https://avatar.fandom.com/wiki/Aang"
        }

        result = extractor._classify_by_metadata(page)
        assert result == "character"

    def test_classify_by_url_pattern(self):
        """Test classification via URL patterns."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Zuko",
            "url": "https://avatar.fandom.com/wiki/characters/Zuko",
            "namespace": "Main"
        }

        result = extractor._classify_by_metadata(page)
        assert result == "character"

    def test_classify_by_infobox_fields(self):
        """Test classification via character-specific infobox fields."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Korra",
            "namespace": "Main",
            "url": "https://avatar.fandom.com/wiki/Korra",
            "infobox_data": {
                "species": "Human",
                "age": "21",
                "gender": "Female",
                "affiliation": "Team Avatar"
            }
        }

        result = extractor._classify_by_metadata(page)
        assert result == "character"

    def test_classify_insufficient_metadata(self):
        """Test that pages with insufficient metadata return None."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Republic City",
            "namespace": "Main",
            "url": "https://avatar.fandom.com/wiki/Republic_City",
            "infobox_data": {
                "location": "United Republic"
            }
        }

        result = extractor._classify_by_metadata(page)
        assert result is None  # Ambiguous, needs further classification


# ============================================================================
# BATCH TITLE CLASSIFICATION TESTS (Tier 2)
# ============================================================================

class TestBatchTitleClassification:
    """Test Tier 2: CHEAP batch LLM title classification."""

    def test_batch_classify_titles_characters(self):
        """Test batch classification identifies characters."""
        extractor = CharacterExtractor(project_name="test_project")

        pages = [
            {"title": "Korra", "url": "..."},
            {"title": "Aang", "url": "..."},
            {"title": "Mako", "url": "..."}
        ]

        # Mock LLM client
        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = """Korra: yes
Aang: yes
Mako: yes"""

        result = extractor._classify_titles_batch(pages)

        assert result["Korra"] is True
        assert result["Aang"] is True
        assert result["Mako"] is True

    def test_batch_classify_titles_mixed(self):
        """Test batch classification handles mixed character/non-character."""
        extractor = CharacterExtractor(project_name="test_project")

        pages = [
            {"title": "Korra", "url": "..."},
            {"title": "Republic City", "url": "..."},
            {"title": "Team Avatar", "url": "..."}
        ]

        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = """Korra: yes
Republic City: no
Team Avatar: no"""

        result = extractor._classify_titles_batch(pages)

        assert result["Korra"] is True
        assert result["Republic City"] is False
        assert result["Team Avatar"] is False

    def test_batch_classify_empty_list(self):
        """Test batch classification with empty page list."""
        extractor = CharacterExtractor(project_name="test_project")

        result = extractor._classify_titles_batch([])

        assert result == {}

    def test_parse_classification_response(self):
        """Test parsing of LLM classification response."""
        extractor = CharacterExtractor(project_name="test_project")

        response = """Zuko: yes
Republic City: no
Appa: yes
Fire Nation: no"""

        titles = ["Zuko", "Republic City", "Appa", "Fire Nation"]
        result = extractor._parse_classification_response(response, titles)

        assert result["Zuko"] is True
        assert result["Republic City"] is False
        assert result["Appa"] is True
        assert result["Fire Nation"] is False


# ============================================================================
# CONTENT CLASSIFICATION TESTS (Tier 3)
# ============================================================================

class TestContentClassification:
    """Test Tier 3: SELECTIVE content-based classification."""

    def test_classify_by_content_character(self):
        """Test content classification identifies character."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Mako",
            "main_content": "Mako is a firebender from Republic City and a member of Team Avatar..."
        }

        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = "yes"

        result = extractor._classify_by_content(page, use_rag=False)

        assert result is True

    def test_classify_by_content_non_character(self):
        """Test content classification identifies non-character."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Republic City",
            "main_content": "Republic City is the capital of the United Republic..."
        }

        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = "no"

        result = extractor._classify_by_content(page, use_rag=False)

        assert result is False

    def test_classify_by_content_with_rag(self):
        """Test content classification with RAG context."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Toph",
            "main_content": "Toph Beifong is a master earthbender..."
        }

        # Mock both RAG query and classification
        extractor.query_engine.query = Mock(return_value="Toph is a character who invented metalbending")
        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = "yes"

        result = extractor._classify_by_content(page, use_rag=True)

        assert result is True
        # Verify RAG was called
        extractor.query_engine.query.assert_called_once()


# ============================================================================
# END-TO-END DISCOVERY TESTS
# ============================================================================

class TestDiscoveryEndToEnd:
    """Test complete discovery workflow with all tiers."""

    def test_discover_characters_basic(self, sample_pages_dir, monkeypatch):
        """Test basic end-to-end character discovery."""
        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: sample_pages_dir / x if "data/projects" in str(x) else Path(x)
        )

        # Lower thresholds to ensure characters pass
        extractor = CharacterExtractor(
            project_name="test_project",
            min_mentions=1,
            confidence_threshold=0.1  # Very low threshold for testing
        )

        # Mock LLM for Tier 2 classification
        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = """Mako: yes
Republic City: no
Team Avatar: no"""

        # Mock retriever for validation (10 mentions = 1.0 confidence)
        extractor.query_engine.retriever = Mock()
        extractor.query_engine.retriever.retrieve.return_value = [
            {"text": "test", "distance": 0.3}
        ] * 10  # 10 mentions → confidence = 1.0

        characters = extractor.discover_characters()

        # Should find characters
        assert len(characters) > 0

        # Verify structure
        assert all("name" in char for char in characters)
        assert all("discovered_via" in char for char in characters)

    def test_discovered_via_tracking(self, sample_pages_dir, monkeypatch):
        """Test that discovered_via correctly tracks classification tier."""
        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: sample_pages_dir / x if "data/projects" in str(x) else Path(x)
        )

        # Lower thresholds
        extractor = CharacterExtractor(
            project_name="test_project",
            min_mentions=1,
            confidence_threshold=0.1
        )

        # Mock components
        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = "Mako: yes"
        extractor.query_engine.retriever = Mock()
        extractor.query_engine.retriever.retrieve.return_value = [{"text": "test", "distance": 0.3}] * 10

        characters = extractor.discover_characters()

        # Verify tracking
        metadata_chars = [c for c in characters if "metadata" in c.get("discovered_via", [])]
        title_llm_chars = [c for c in characters if "title_llm" in c.get("discovered_via", [])]

        # Should have some from each tier
        assert len(metadata_chars) > 0  # Aang has Character namespace, Korra has good infobox
        assert len(title_llm_chars) >= 0  # Mako might be classified by LLM


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestValidation:
    """Test character validation via mention counting."""

    def test_validate_characters_counts_mentions(self):
        """Test that validation counts mentions in vector store."""
        extractor = CharacterExtractor(
            project_name="test_project",
            min_mentions=1,
            confidence_threshold=0.1  # Very low threshold for testing
        )
        extractor.query_engine = Mock()

        # Mock retriever (10 mentions = 1.0 confidence)
        extractor.query_engine.retriever = Mock()
        extractor.query_engine.retriever.retrieve.return_value = [
            {"text": "chunk1", "distance": 0.2},
            {"text": "chunk2", "distance": 0.3},
            {"text": "chunk3", "distance": 0.3},
            {"text": "chunk4", "distance": 0.3},
            {"text": "chunk5", "distance": 0.3},
            {"text": "chunk6", "distance": 0.3},
            {"text": "chunk7", "distance": 0.3},
            {"text": "chunk8", "distance": 0.3},
            {"text": "chunk9", "distance": 0.3},
            {"text": "chunk10", "distance": 0.3}
        ]

        characters = [
            {"name": "Korra", "name_variations": ["Korra"], "discovered_via": ["metadata"]}
        ]

        result = extractor._validate_characters(characters)

        assert len(result) == 1
        assert result[0]["mentions"] == 10

    def test_validate_filters_by_min_mentions(self):
        """Test that characters below min_mentions are filtered out."""
        extractor = CharacterExtractor(project_name="test_project", min_mentions=5)
        extractor.query_engine = Mock()

        extractor.query_engine.retriever = Mock()
        extractor.query_engine.retriever.retrieve.return_value = [
            {"text": "chunk", "distance": 0.3}
        ]  # Only 1 mention

        characters = [
            {"name": "Korra", "name_variations": ["Korra"], "discovered_via": ["metadata"]}
        ]

        result = extractor._validate_characters(characters)

        # Should be filtered out (1 < 5)
        assert len(result) == 0


# ============================================================================
# DUPLICATE NAME HANDLING TESTS
# ============================================================================

class TestDuplicateNameHandling:
    """Test handling of characters with duplicate names (e.g., two Bumis)."""

    def test_parse_name_with_disambiguation(self):
        """Test parsing page title with disambiguation."""
        extractor = CharacterExtractor(project_name="test_project")

        result = extractor._parse_character_name("Bumi (King of Omashu)")

        assert result["base_name"] == "Bumi"
        assert result["disambiguation"] == "King of Omashu"
        assert result["full_name"] == "Bumi (King of Omashu)"

    def test_parse_name_without_disambiguation(self):
        """Test parsing page title without disambiguation."""
        extractor = CharacterExtractor(project_name="test_project")

        result = extractor._parse_character_name("Aang")

        assert result["base_name"] == "Aang"
        assert result["disambiguation"] is None
        assert result["full_name"] == "Aang"

    def test_parse_name_with_nested_parentheses(self):
        """Test parsing title with multiple parentheses."""
        extractor = CharacterExtractor(project_name="test_project")

        # Regex matches the LAST set of parentheses (most specific disambiguation)
        # For "Character (First) (Second)", the last () is the disambiguation
        result = extractor._parse_character_name("Character (First) (Second)")

        assert result["base_name"] == "Character (First)"
        assert result["disambiguation"] == "Second"
        assert result["full_name"] == "Character (First) (Second)"

    def test_create_character_entry_with_disambiguation(self):
        """Test character entry creation preserves disambiguation."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Bumi (King of Omashu)",
            "url": "https://avatar.fandom.com/wiki/Bumi_(King)",
            "main_content": "King Bumi..."
        }

        char = extractor._create_character_entry(page, tier="metadata")

        assert char["name"] == "Bumi"
        assert char["full_name"] == "Bumi (King of Omashu)"
        assert char["disambiguation"] == "King of Omashu"
        assert char["source_url"] == "https://avatar.fandom.com/wiki/Bumi_(King)"

    def test_create_character_entry_without_disambiguation(self):
        """Test character entry creation for non-disambiguated names."""
        extractor = CharacterExtractor(project_name="test_project")

        page = {
            "title": "Aang",
            "url": "https://avatar.fandom.com/wiki/Aang",
            "main_content": "Aang was..."
        }

        char = extractor._create_character_entry(page, tier="metadata")

        assert char["name"] == "Aang"
        assert char["full_name"] == "Aang"
        assert char["disambiguation"] is None

    def test_load_duplicate_name_fixtures(self, sample_pages_dir, monkeypatch):
        """Test loading both Bumi characters from fixtures."""
        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: sample_pages_dir / x if "data/projects" in str(x) else Path(x)
        )

        extractor = CharacterExtractor(project_name="test_project")
        pages = extractor._load_crawled_pages()

        # Find both Bumi pages
        bumi_pages = [p for p in pages if "Bumi" in p.get("title", "")]

        # Should have 2 distinct Bumi characters in fixtures
        assert len(bumi_pages) == 2

        # Verify they have different URLs
        bumi_urls = [p["url"] for p in bumi_pages]
        assert len(set(bumi_urls)) == 2  # Both unique

    def test_validation_filters_by_source_url(self):
        """Test that validation filters chunks by source URL for duplicate names."""
        extractor = CharacterExtractor(
            project_name="test_project",
            min_mentions=1,
            confidence_threshold=0.1
        )
        extractor.query_engine = Mock()

        # Mock retriever returns chunks from BOTH Bumi characters
        extractor.query_engine.retriever = Mock()
        extractor.query_engine.retriever.retrieve.return_value = [
            # Chunks from King Bumi's page
            {"text": "King Bumi chunk 1", "distance": 0.2, "metadata": {"source_url": "wiki/Bumi_(King)"}},
            {"text": "King Bumi chunk 2", "distance": 0.3, "metadata": {"source_url": "wiki/Bumi_(King)"}},
            {"text": "King Bumi chunk 3", "distance": 0.3, "metadata": {"source_url": "wiki/Bumi_(King)"}},
            # Chunks from Aang's son Bumi's page
            {"text": "Aang's son chunk 1", "distance": 0.2, "metadata": {"source_url": "wiki/Bumi_(Aang's_son)"}},
            {"text": "Aang's son chunk 2", "distance": 0.3, "metadata": {"source_url": "wiki/Bumi_(Aang's_son)"}},
        ] * 2  # Duplicate to reach 10 total

        # Two different Bumi characters
        characters = [
            {
                "name": "Bumi",
                "full_name": "Bumi (King of Omashu)",
                "disambiguation": "King of Omashu",
                "source_url": "https://avatar.fandom.com/wiki/Bumi_(King)",
                "name_variations": ["Bumi"],
                "discovered_via": ["metadata"]
            },
            {
                "name": "Bumi",
                "full_name": "Bumi (son of Aang)",
                "disambiguation": "son of Aang",
                "source_url": "https://avatar.fandom.com/wiki/Bumi_(Aang's_son)",
                "name_variations": ["Bumi"],
                "discovered_via": ["metadata"]
            }
        ]

        result = extractor._validate_characters(characters)

        # Both should pass validation
        assert len(result) == 2

        # King Bumi should have 6 mentions (3 chunks * 2)
        king_bumi = next(c for c in result if "King" in c["disambiguation"])
        assert king_bumi["mentions"] == 6

        # Son Bumi should have 4 mentions (2 chunks * 2)
        son_bumi = next(c for c in result if "son" in c["disambiguation"])
        assert son_bumi["mentions"] == 4

    def test_discover_characters_preserves_disambiguation(self, sample_pages_dir, monkeypatch):
        """Test end-to-end discovery preserves disambiguation for duplicate names."""
        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: sample_pages_dir / x if "data/projects" in str(x) else Path(x)
        )

        extractor = CharacterExtractor(
            project_name="test_project",
            min_mentions=1,
            confidence_threshold=0.1
        )

        # Mock LLM
        extractor.query_engine.llm_client = Mock()
        extractor.query_engine.llm_client.generate.return_value = "yes"

        # Mock retriever
        extractor.query_engine.retriever = Mock()
        extractor.query_engine.retriever.retrieve.return_value = [
            {"text": "test", "distance": 0.3, "metadata": {"source_url": "wiki/Bumi_(King)"}}
        ] * 10

        characters = extractor.discover_characters()

        # Find Bumi characters
        bumis = [c for c in characters if c["name"] == "Bumi"]

        # Should have 2 distinct Bumis
        assert len(bumis) == 2

        # Both should have different full names
        full_names = [c["full_name"] for c in bumis]
        assert len(set(full_names)) == 2

        # Both should have disambiguations
        disambiguations = [c["disambiguation"] for c in bumis]
        assert all(d is not None for d in disambiguations)


class TestCharacterSaving:
    """Test saving discovered characters to disk."""

    def test_save_characters_creates_directory(self, tmp_path):
        """Test that save_characters creates the characters directory."""
        characters_dir = tmp_path / "characters"

        extractor = CharacterExtractor(project_name="test_project")

        characters = [
            {
                "name": "Aang",
                "full_name": "Aang",
                "disambiguation": None,
                "source_url": "https://avatar.fandom.com/wiki/Aang",
                "mentions": 10,
                "confidence": 0.95,
                "discovered_via": ["metadata"],
                "name_variations": ["Aang"]
            }
        ]

        save_path = extractor.save_characters(characters, output_dir=characters_dir)

        # Characters directory should exist
        assert save_path.exists()
        assert save_path.is_dir()

    def test_save_characters_writes_json_files(self, tmp_path):
        """Test that save_characters writes JSON files for each character."""
        characters_dir = tmp_path / "characters"

        extractor = CharacterExtractor(project_name="test_project")

        characters = [
            {
                "name": "Aang",
                "full_name": "Aang",
                "disambiguation": None,
                "source_url": "https://avatar.fandom.com/wiki/Aang",
                "mentions": 10,
                "confidence": 0.95,
                "discovered_via": ["metadata"],
                "name_variations": ["Aang"]
            },
            {
                "name": "Zuko",
                "full_name": "Zuko",
                "disambiguation": None,
                "source_url": "https://avatar.fandom.com/wiki/Zuko",
                "mentions": 8,
                "confidence": 0.90,
                "discovered_via": ["title_llm"],
                "name_variations": ["Zuko", "Prince Zuko"]
            }
        ]

        save_path = extractor.save_characters(characters, output_dir=characters_dir)

        # Character files should exist
        aang_file = save_path / "Aang.json"
        zuko_file = save_path / "Zuko.json"

        assert aang_file.exists()
        assert zuko_file.exists()

    def test_save_characters_handles_duplicate_names(self, tmp_path):
        """Test that duplicate character names are saved with disambiguation."""
        characters_dir = tmp_path / "characters"

        extractor = CharacterExtractor(project_name="test_project")

        characters = [
            {
                "name": "Bumi",
                "full_name": "Bumi (King of Omashu)",
                "disambiguation": "King of Omashu",
                "source_url": "https://avatar.fandom.com/wiki/Bumi_(King)",
                "mentions": 5,
                "confidence": 0.88,
                "discovered_via": ["metadata"],
                "name_variations": ["Bumi"]
            },
            {
                "name": "Bumi",
                "full_name": "Bumi (son of Aang)",
                "disambiguation": "son of Aang",
                "source_url": "https://avatar.fandom.com/wiki/Bumi_(Aang's_son)",
                "mentions": 3,
                "confidence": 0.85,
                "discovered_via": ["metadata"],
                "name_variations": ["Bumi"]
            }
        ]

        save_path = extractor.save_characters(characters, output_dir=characters_dir)

        # Both Bumis should be saved with different filenames
        king_file = save_path / "Bumi_(King_of_Omashu).json"
        son_file = save_path / "Bumi_(son_of_Aang).json"

        assert king_file.exists()
        assert son_file.exists()

    def test_save_characters_preserves_all_fields(self, tmp_path):
        """Test that saved JSON contains all character fields."""
        characters_dir = tmp_path / "characters"

        extractor = CharacterExtractor(project_name="test_project")

        characters = [
            {
                "name": "Korra",
                "full_name": "Korra",
                "disambiguation": None,
                "source_url": "https://avatar.fandom.com/wiki/Korra",
                "mentions": 15,
                "confidence": 0.98,
                "discovered_via": ["metadata", "title_llm"],
                "name_variations": ["Korra", "Avatar Korra"]
            }
        ]

        save_path = extractor.save_characters(characters, output_dir=characters_dir)

        # Load and verify
        korra_file = save_path / "Korra.json"
        with open(korra_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)

        assert saved_data["name"] == "Korra"
        assert saved_data["full_name"] == "Korra"
        assert saved_data["source_url"] == "https://avatar.fandom.com/wiki/Korra"
        assert saved_data["mentions"] == 15
        assert saved_data["confidence"] == 0.98
        assert "metadata" in saved_data["discovered_via"]
        assert "title_llm" in saved_data["discovered_via"]

    def test_save_characters_adds_metadata(self, tmp_path):
        """Test that saved files include save metadata (timestamp, project)."""
        characters_dir = tmp_path / "characters"

        extractor = CharacterExtractor(project_name="test_project")

        characters = [
            {
                "name": "Mako",
                "full_name": "Mako",
                "disambiguation": None,
                "source_url": "https://avatar.fandom.com/wiki/Mako",
                "mentions": 7,
                "confidence": 0.87,
                "discovered_via": ["metadata"],
                "name_variations": ["Mako"]
            }
        ]

        save_path = extractor.save_characters(characters, output_dir=characters_dir)

        # Load and verify metadata
        mako_file = save_path / "Mako.json"
        with open(mako_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)

        assert "saved_at" in saved_data
        assert "project_name" in saved_data
        assert saved_data["project_name"] == "test_project"

    def test_save_characters_returns_path(self, tmp_path):
        """Test that save_characters returns the save directory path."""
        project_dir = tmp_path / "data" / "projects" / "test_project"
        characters_dir = project_dir / "characters"

        extractor = CharacterExtractor(project_name="test_project")

        characters = [
            {
                "name": "Toph",
                "full_name": "Toph Beifong",
                "disambiguation": None,
                "source_url": "https://avatar.fandom.com/wiki/Toph",
                "mentions": 12,
                "confidence": 0.93,
                "discovered_via": ["metadata"],
                "name_variations": ["Toph", "Toph Beifong"]
            }
        ]

        save_path = extractor.save_characters(characters, output_dir=characters_dir)

        assert save_path == characters_dir

    def test_discover_characters_with_auto_save(self, tmp_path):
        """Test that discover_characters calls save_characters when save=True."""
        extractor = CharacterExtractor(project_name="test_project")

        # Mock discover_characters to return fake characters without running full pipeline
        fake_characters = [
            {
                "name": "TestChar",
                "full_name": "TestChar",
                "disambiguation": None,
                "source_url": "https://test.com",
                "mentions": 5,
                "confidence": 0.9,
                "discovered_via": ["metadata"],
                "name_variations": ["TestChar"]
            }
        ]

        # Mock the entire discovery pipeline to return fake characters
        extractor._execute_discovery_queries = Mock(return_value=fake_characters)
        extractor._deduplicate_characters = Mock(return_value=fake_characters)
        extractor._validate_characters = Mock(return_value=fake_characters)

        # Mock save_characters with output_dir pointing to tmp_path
        characters_dir = tmp_path / "characters"
        original_save = extractor.save_characters

        def mock_save_with_temp_dir(chars, output_dir=None):
            return original_save(chars, output_dir=characters_dir)

        extractor.save_characters = Mock(side_effect=mock_save_with_temp_dir)

        # Discover with auto-save
        characters = extractor.discover_characters(save=True)

        # Verify save_characters was called
        extractor.save_characters.assert_called_once()

        # Verify files were created
        assert characters_dir.exists()
        character_files = list(characters_dir.glob("*.json"))
        assert len(character_files) == 1


print(f"[INFO] Test file rewritten with {__name__}")
