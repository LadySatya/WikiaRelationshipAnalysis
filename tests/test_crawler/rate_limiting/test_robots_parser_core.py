"""
HIGH-QUALITY tests for RobotsParser.

Tests robots.txt parsing, caching, and compliance checking.
"""

import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.crawler.rate_limiting.robots_parser import RobotsParser

pytestmark = pytest.mark.unit


class TestRobotsParserInitialization:
    """Test RobotsParser initialization and validation."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_init_with_valid_user_agent(self, temp_cache_dir):
        """Should initialize with valid user agent."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        assert parser.user_agent == "TestBot/1.0"
        assert parser.cache_dir == temp_cache_dir

    def test_init_validates_empty_user_agent(self, temp_cache_dir):
        """Should reject empty user agent."""
        with pytest.raises(ValueError, match="User agent cannot be empty"):
            RobotsParser(user_agent="", cache_dir=temp_cache_dir)

    def test_init_validates_whitespace_user_agent(self, temp_cache_dir):
        """Should reject whitespace-only user agent."""
        with pytest.raises(ValueError, match="User agent cannot be empty"):
            RobotsParser(user_agent="   ", cache_dir=temp_cache_dir)

    def test_init_validates_none_user_agent(self, temp_cache_dir):
        """Should reject None user agent."""
        with pytest.raises(ValueError, match="User agent cannot be None"):
            RobotsParser(user_agent=None, cache_dir=temp_cache_dir)

    def test_init_creates_cache_directory(self, temp_cache_dir):
        """Should create cache directory if it doesn't exist."""
        cache_path = temp_cache_dir / "robots_cache"

        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=cache_path)

        assert cache_path.exists()
        assert cache_path.is_dir()

    def test_init_accepts_custom_cache_ttl(self, temp_cache_dir):
        """Should accept custom cache TTL."""
        parser = RobotsParser(
            user_agent="TestBot/1.0", cache_dir=temp_cache_dir, cache_ttl_hours=48
        )

        assert parser.cache_ttl_hours == 48


class TestCanFetchValidation:
    """Test can_fetch URL validation."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_can_fetch_rejects_empty_url(self, temp_cache_dir):
        """Should return False for empty URL."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        result = await parser.can_fetch("")

        assert result is False

    @pytest.mark.asyncio
    async def test_can_fetch_rejects_non_string_url(self, temp_cache_dir):
        """Should return False for non-string URL."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        result = await parser.can_fetch(None)

        assert result is False

    @pytest.mark.asyncio
    async def test_can_fetch_handles_malformed_url(self, temp_cache_dir):
        """Should handle malformed URL gracefully."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        # URL with no domain
        result = await parser.can_fetch("notavalidurl")

        # Should default to allowing (fail-open)
        assert result is False  # Can't extract domain


class TestRobotsTxtParsing:
    """Test robots.txt parsing logic."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_can_fetch_allows_when_no_robots_txt(self, temp_cache_dir):
        """Should allow fetching when robots.txt doesn't exist (404)."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        # Mock _fetch_robots_txt to return None (404)
        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = None

            result = await parser.can_fetch("https://example.com/page")

            assert result is True  # Allow by default

    @pytest.mark.asyncio
    async def test_can_fetch_respects_disallow_rule(self, temp_cache_dir):
        """Should respect Disallow rules in robots.txt."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = """
User-agent: *
Disallow: /admin/
Disallow: /private/
"""

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            # Should disallow /admin/ paths
            result = await parser.can_fetch("https://example.com/admin/users")
            assert result is False

            # Should allow other paths
            result = await parser.can_fetch("https://example.com/public/page")
            assert result is True

    @pytest.mark.asyncio
    async def test_can_fetch_respects_user_agent_specific_rules(self, temp_cache_dir):
        """Should use user-agent specific rules when available."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = """
User-agent: TestBot
Disallow: /secret/

User-agent: *
Disallow: /admin/
"""

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            # TestBot should be blocked from /secret/ but not /admin/
            result = await parser.can_fetch("https://example.com/secret/file")
            assert result is False

            result = await parser.can_fetch("https://example.com/admin/page")
            assert result is True  # TestBot has specific rules, ignores wildcard

    @pytest.mark.asyncio
    async def test_can_fetch_allows_everything_when_empty_robots(self, temp_cache_dir):
        """Should allow everything when robots.txt is empty."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = ""

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            result = await parser.can_fetch("https://example.com/anything")
            assert result is True


class TestCrawlDelay:
    """Test crawl delay extraction from robots.txt."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_get_crawl_delay_returns_none_when_no_robots(self, temp_cache_dir):
        """Should return None when robots.txt doesn't exist."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = None

            delay = await parser.get_crawl_delay("https://example.com/page")

            assert delay is None

    @pytest.mark.asyncio
    async def test_get_crawl_delay_extracts_delay_from_robots(self, temp_cache_dir):
        """Should extract Crawl-delay from robots.txt."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = """
User-agent: *
Crawl-delay: 2
"""

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            delay = await parser.get_crawl_delay("https://example.com/page")

            assert delay == 2.0

    @pytest.mark.asyncio
    async def test_get_crawl_delay_respects_user_agent_specific_delay(
        self, temp_cache_dir
    ):
        """Should use user-agent specific crawl delay."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = """
User-agent: TestBot
Crawl-delay: 5

User-agent: *
Crawl-delay: 2
"""

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            delay = await parser.get_crawl_delay("https://example.com/page")

            # Should use TestBot-specific delay, not wildcard
            assert delay == 5.0

    @pytest.mark.asyncio
    async def test_get_crawl_delay_validates_empty_url(self, temp_cache_dir):
        """Should return None for empty URL."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        delay = await parser.get_crawl_delay("")

        assert delay is None

    @pytest.mark.asyncio
    async def test_get_crawl_delay_validates_malformed_url(self, temp_cache_dir):
        """Should return None for malformed URL."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        delay = await parser.get_crawl_delay("notavalidurl")

        assert delay is None


class TestCaching:
    """Test robots.txt caching logic."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_caches_robots_txt_in_memory(self, temp_cache_dir):
        """Should cache robots.txt in memory after first fetch."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = "User-agent: *\nDisallow: /admin/"

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            # First call - should fetch
            await parser.can_fetch("https://example.com/page1")
            assert mock_fetch.call_count == 1

            # Second call - should use cache
            await parser.can_fetch("https://example.com/page2")
            assert mock_fetch.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self, temp_cache_dir):
        """Should refetch robots.txt after cache TTL expires."""
        # Use very short TTL for testing
        parser = RobotsParser(
            user_agent="TestBot/1.0",
            cache_dir=temp_cache_dir,
            cache_ttl_hours=0.0001,  # ~0.36 seconds
        )

        robots_content = "User-agent: *\nDisallow: /admin/"

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            # First call - should fetch
            await parser.can_fetch("https://example.com/page")
            assert mock_fetch.call_count == 1

            # Manually expire both in-memory and file cache
            if "example.com" in parser._robots_cache:
                robots_parser, _ = parser._robots_cache["example.com"]
                parser._robots_cache["example.com"] = (
                    robots_parser,
                    time.time() - 7200,
                )  # 2 hours ago

            # Also delete file cache to force refetch
            cache_path = parser._get_cache_path("example.com")
            if cache_path.exists():
                cache_path.unlink()

            # Next call - should refetch (cache expired)
            await parser.can_fetch("https://example.com/page")
            assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_saves_robots_txt_to_file_cache(self, temp_cache_dir):
        """Should save robots.txt to file cache."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = "User-agent: *\nDisallow: /admin/"

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            await parser.can_fetch("https://example.com/page")

            # Check that cache file was created
            cache_path = parser._get_cache_path("example.com")
            assert cache_path.exists()

    @pytest.mark.asyncio
    async def test_loads_from_file_cache_on_new_instance(self, temp_cache_dir):
        """Should load from file cache when creating new parser instance."""
        robots_content = "User-agent: *\nDisallow: /admin/"

        # First parser - fetch and cache
        parser1 = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        with patch.object(
            parser1, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content
            await parser1.can_fetch("https://example.com/page")

        # Second parser - should load from file cache
        parser2 = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        with patch.object(
            parser2, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch2:
            mock_fetch2.return_value = robots_content

            # Should use file cache, not fetch
            result = await parser2.can_fetch("https://example.com/admin/page")

            assert result is False  # Rules applied
            mock_fetch2.assert_not_called()  # Didn't need to fetch


class TestCachePathGeneration:
    """Test cache file path generation."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_get_cache_path_generates_consistent_path(self, temp_cache_dir):
        """Should generate same path for same domain."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        path1 = parser._get_cache_path("example.com")
        path2 = parser._get_cache_path("example.com")

        assert path1 == path2

    def test_get_cache_path_generates_different_paths_for_different_domains(
        self, temp_cache_dir
    ):
        """Should generate different paths for different domains."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        path1 = parser._get_cache_path("example.com")
        path2 = parser._get_cache_path("another.com")

        assert path1 != path2

    def test_get_cache_path_handles_special_characters(self, temp_cache_dir):
        """Should handle domains with special characters."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        # Should not crash with special characters
        path = parser._get_cache_path("sub.example.com")

        assert path is not None
        assert str(path).startswith(str(temp_cache_dir))


class TestCacheClearance:
    """Test cache clearing functionality."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_clear_cache_removes_memory_cache(self, temp_cache_dir):
        """Should clear in-memory cache."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = "User-agent: *\nDisallow: /admin/"

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            # Fetch and cache
            await parser.can_fetch("https://example.com/page")
            assert len(parser._robots_cache) > 0

            # Clear cache
            parser.clear_cache()

            # Memory cache should be empty
            assert len(parser._robots_cache) == 0

    @pytest.mark.asyncio
    async def test_clear_cache_removes_file_cache(self, temp_cache_dir):
        """Should remove cached files from disk."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        robots_content = "User-agent: *\nDisallow: /admin/"

        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = robots_content

            # Fetch and cache
            await parser.can_fetch("https://example.com/page")

            cache_path = parser._get_cache_path("example.com")
            assert cache_path.exists()

            # Clear cache
            parser.clear_cache()

            # File cache should be removed
            assert not cache_path.exists()


class TestErrorHandling:
    """Test error handling in robots.txt operations."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_can_fetch_allows_on_network_error(self, temp_cache_dir):
        """Should allow fetching when network error occurs (fail-open)."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        # Mock fetch to raise exception
        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            result = await parser.can_fetch("https://example.com/page")

            # Should fail open (allow)
            assert result is True

    @pytest.mark.asyncio
    async def test_get_crawl_delay_returns_none_on_error(self, temp_cache_dir):
        """Should return None when error occurs getting delay."""
        parser = RobotsParser(user_agent="TestBot/1.0", cache_dir=temp_cache_dir)

        # Mock fetch to raise exception
        with patch.object(
            parser, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            delay = await parser.get_crawl_delay("https://example.com/page")

            assert delay is None
