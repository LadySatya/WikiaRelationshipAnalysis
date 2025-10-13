"""
Tests for WikiaCrawler initialization.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.crawler.core.crawler import WikiaCrawler

# Mark all tests in this module as unit tests (all use mocks, no real I/O)
pytestmark = pytest.mark.unit


class TestWikiaCrawlerInit:
    """Test WikiaCrawler initialization with various configurations."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def basic_config(self):
        """Basic valid configuration for testing."""
        return {
            "respect_robots_txt": True,
            "user_agent": "WikiaAnalyzer/0.1.0",
            "default_delay_seconds": 1.0,
            "timeout_seconds": 30,
            "max_retries": 3,
            "target_namespaces": ["Main", "Character"],
            "exclude_patterns": ["User:", "Template:"],
            "save_state_every_n_pages": 10,
        }

    def test_init_with_valid_config(self, basic_config):
        """Test initialization with valid configuration."""
        project_name = "naruto_wiki"
        crawler = WikiaCrawler(project_name, basic_config)

        # Should create instance without errors
        assert crawler is not None
        assert hasattr(crawler, "project_name")
        assert hasattr(crawler, "config")

    def test_init_stores_project_name(self, basic_config):
        """Test that project name is properly stored."""
        project_name = "bleach_wiki"
        crawler = WikiaCrawler(project_name, basic_config)

        assert crawler.project_name == project_name

    def test_init_stores_config(self, basic_config):
        """Test that configuration is properly stored."""
        crawler = WikiaCrawler("test_project", basic_config)

        assert crawler.config == basic_config
        assert crawler.config["respect_robots_txt"] is True
        assert crawler.config["default_delay_seconds"] == 1.0

    def test_init_with_empty_project_name(self, basic_config):
        """Test initialization with empty project name should raise error."""
        with pytest.raises(ValueError, match="Project name cannot be empty"):
            WikiaCrawler("", basic_config)

    def test_init_with_none_project_name(self, basic_config):
        """Test initialization with None project name should raise error."""
        with pytest.raises(ValueError, match="Project name cannot be None"):
            WikiaCrawler(None, basic_config)

    def test_init_with_invalid_project_name_chars(self, basic_config):
        """Test initialization with invalid characters in project name."""
        invalid_names = [
            "project/with/slashes",
            "project\\with\\backslashes",
            "project:with:colons",
            "project*with*asterisks",
            "project?with?questions",
        ]

        for invalid_name in invalid_names:
            with pytest.raises(
                ValueError, match="Project name contains invalid characters"
            ):
                WikiaCrawler(invalid_name, basic_config)

    def test_init_with_none_config(self):
        """Test initialization with None config should raise error."""
        with pytest.raises(ValueError, match="Configuration cannot be None"):
            WikiaCrawler("test_project", None)

    def test_init_with_empty_config(self):
        """Test initialization with empty config should raise error."""
        with pytest.raises(ValueError, match="Configuration cannot be empty"):
            WikiaCrawler("test_project", {})

    def test_init_validates_required_config_keys(self, basic_config):
        """Test that required configuration keys are validated."""
        required_keys = [
            "respect_robots_txt",
            "user_agent",
            "default_delay_seconds",
            "target_namespaces",
        ]

        for key in required_keys:
            incomplete_config = basic_config.copy()
            del incomplete_config[key]

            with pytest.raises(
                ValueError, match=f"Missing required configuration key: {key}"
            ):
                WikiaCrawler("test_project", incomplete_config)

    def test_init_validates_config_types(self, basic_config):
        """Test that configuration value types are validated."""
        # Test boolean validation
        bad_config = basic_config.copy()
        bad_config["respect_robots_txt"] = "true"  # Should be boolean
        with pytest.raises(ValueError, match="respect_robots_txt must be a boolean"):
            WikiaCrawler("test_project", bad_config)

        # Test numeric validation
        bad_config = basic_config.copy()
        bad_config["default_delay_seconds"] = "1.0"  # Should be float
        with pytest.raises(ValueError, match="default_delay_seconds must be a number"):
            WikiaCrawler("test_project", bad_config)

        # Test list validation
        bad_config = basic_config.copy()
        bad_config["target_namespaces"] = "Main,Character"  # Should be list
        with pytest.raises(ValueError, match="target_namespaces must be a list"):
            WikiaCrawler("test_project", bad_config)

    def test_init_creates_project_directory_structure(
        self, basic_config, temp_project_dir
    ):
        """Test that initialization creates proper project directory structure."""
        with (
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("src.crawler.core.crawler.Path") as mock_path,
        ):

            # Setup mock to use our temp directory
            mock_path.return_value = temp_project_dir

            crawler = WikiaCrawler("test_project", basic_config)

            # Verify directory creation was attempted
            assert mock_mkdir.called

    def test_init_sets_default_values(self):
        """Test that initialization sets sensible defaults for optional config."""
        minimal_config = {
            "respect_robots_txt": True,
            "user_agent": "WikiaAnalyzer/0.1.0",
            "default_delay_seconds": 1.0,
            "target_namespaces": ["Main"],
        }

        crawler = WikiaCrawler("test_project", minimal_config)

        # Should set defaults for optional values
        assert hasattr(crawler, "timeout_seconds")
        assert hasattr(crawler, "max_retries")
        assert hasattr(crawler, "exclude_patterns")

    @patch("src.crawler.core.crawler.URLManager")
    @patch("src.crawler.core.crawler.SessionManager")
    @patch("src.crawler.core.crawler.RateLimiter")
    def test_init_creates_component_instances(
        self, mock_rate_limiter, mock_session_manager, mock_url_manager, basic_config
    ):
        """Test that initialization creates necessary component instances."""
        crawler = WikiaCrawler("test_project", basic_config)

        # Should create instances of key components
        assert hasattr(crawler, "rate_limiter")
        assert hasattr(crawler, "session_manager")
        assert hasattr(crawler, "url_manager")
        assert hasattr(crawler, "content_saver")
        assert hasattr(crawler, "crawl_state")

    def test_init_with_custom_data_dir(self, basic_config, temp_project_dir):
        """Test initialization with custom data directory."""
        config_with_data_dir = basic_config.copy()
        config_with_data_dir["data_dir"] = str(temp_project_dir)

        crawler = WikiaCrawler("test_project", config_with_data_dir)

        # Should use custom data directory
        expected_project_path = temp_project_dir / "projects" / "test_project"
        assert crawler.project_path == expected_project_path
