"""
Tests for PageExtractor class - focused on link extraction filtering.
"""

from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

from src.crawler.extraction.page_extractor import PageExtractor

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


class TestPageExtractorLinkFiltering:
    """Test PageExtractor link extraction with same-domain filtering."""

    @pytest.fixture
    def page_extractor(self):
        """Create PageExtractor instance for testing."""
        return PageExtractor()

    def test_extract_links_filters_same_wikia_domain_only(self, page_extractor):
        """Test that extract_links only returns links from same wikia domain."""
        html = """
        <html>
        <body>
            <a href="/wiki/Character_A">Character A</a>
            <a href="https://avatar.fandom.com/wiki/Character_B">Character B</a>
            <a href="https://naruto.fandom.com/wiki/Naruto">Naruto (different wiki)</a>
            <a href="https://twitter.com/avatar">Twitter</a>
            <a href="https://community.fandom.com/wiki/Help">Fandom Help</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://avatar.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        # Should only include avatar.fandom.com links
        assert all("avatar.fandom.com" in link for link in links)

        # Should have 2 links (relative and absolute from same wiki)
        assert len(links) == 2

        # Should NOT include other wikis
        assert not any("naruto.fandom.com" in link for link in links)

        # Should NOT include external sites
        assert not any("twitter.com" in link for link in links)

        # Should NOT include meta-platform domains
        assert not any("community.fandom.com" in link for link in links)

    def test_extract_links_includes_relative_urls(self, page_extractor):
        """Test that relative URLs are converted to absolute and included."""
        html = """
        <html>
        <body>
            <a href="/wiki/Page1">Page 1</a>
            <a href="/wiki/Page2">Page 2</a>
            <a href="/wiki/Category:Characters">Characters Category</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://buffy.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        # All links should be absolute
        assert all(link.startswith("https://") for link in links)

        # All should be from buffy.fandom.com
        assert all("buffy.fandom.com" in link for link in links)

        # Should have 3 links
        assert len(links) == 3

    def test_extract_links_excludes_fragments(self, page_extractor):
        """Test that fragment-only links are excluded."""
        html = """
        <html>
        <body>
            <a href="#section1">Section 1</a>
            <a href="#section2">Section 2</a>
            <a href="/wiki/RealPage">Real Page</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://avatar.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        # Should only have 1 link (the real page, not fragments)
        assert len(links) == 1
        assert "/wiki/RealPage" in links[0]

    def test_extract_links_excludes_external_wikis(self, page_extractor):
        """Test that links to different wikis are excluded."""
        html = """
        <html>
        <body>
            <a href="https://buffy.fandom.com/wiki/Buffy">Buffy (same wiki)</a>
            <a href="https://naruto.fandom.com/wiki/Naruto">Naruto (different wiki)</a>
            <a href="https://harrypotter.fandom.com/wiki/Harry">Harry (different wiki)</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://buffy.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        # Should only have 1 link from buffy wiki
        assert len(links) == 1
        assert "buffy.fandom.com" in links[0]

    def test_extract_links_excludes_fandom_meta_domains(self, page_extractor):
        """Test that Fandom meta-platform domains are excluded."""
        html = """
        <html>
        <body>
            <a href="https://avatar.fandom.com/wiki/Aang">Aang</a>
            <a href="https://community.fandom.com/wiki/Central">Community Central</a>
            <a href="https://about.fandom.com/careers">Careers</a>
            <a href="https://auth.fandom.com/signin">Sign In</a>
            <a href="https://fandom.zendesk.com/help">Help</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://avatar.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        # Should only have 1 link (the avatar wiki link)
        assert len(links) == 1
        assert "avatar.fandom.com" in links[0]

        # Should NOT include any meta domains
        meta_domains = [
            "community.fandom.com",
            "about.fandom.com",
            "auth.fandom.com",
            "fandom.zendesk.com",
        ]
        for link in links:
            assert not any(meta in link for meta in meta_domains)

    def test_extract_links_removes_duplicates(self, page_extractor):
        """Test that duplicate links are removed."""
        html = """
        <html>
        <body>
            <a href="/wiki/Aang">Aang 1</a>
            <a href="/wiki/Aang">Aang 2</a>
            <a href="https://avatar.fandom.com/wiki/Aang">Aang 3</a>
            <a href="/wiki/Katara">Katara</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://avatar.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        # Should have 2 unique links (Aang and Katara)
        assert len(links) == 2

        # Should have one link with Aang
        aang_links = [link for link in links if "Aang" in link]
        assert len(aang_links) == 1

    def test_extract_links_handles_empty_soup(self, page_extractor):
        """Test that empty soup returns empty list."""
        base_url = "https://avatar.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(None, base_url)

        assert links == []

    def test_extract_links_handles_no_links(self, page_extractor):
        """Test page with no links returns empty list."""
        html = """
        <html>
        <body>
            <p>This page has no links.</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://avatar.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        assert links == []

    def test_extract_links_handles_mixed_link_formats(self, page_extractor):
        """Test extraction with various URL formats."""
        html = """
        <html>
        <body>
            <a href="/wiki/Page1">Relative path</a>
            <a href="https://avatar.fandom.com/wiki/Page2">Absolute URL</a>
            <a href="//avatar.fandom.com/wiki/Page3">Protocol-relative</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://avatar.fandom.com/wiki/Main_Page"

        links = page_extractor.extract_links(soup, base_url)

        # All 3 should be included as they're from same wiki
        assert len(links) == 3

        # All should be absolute URLs
        assert all(link.startswith("https://") for link in links)


class TestPageExtractorInit:
    """Test PageExtractor initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        extractor = PageExtractor()

        assert extractor.config is not None
        assert "title_selectors" in extractor.config
        assert "content_selectors" in extractor.config
        assert "ignore_selectors" in extractor.config

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        custom_config = {
            "title_selectors": [".custom-title"],
            "min_content_length": 100,
        }

        extractor = PageExtractor(config=custom_config)

        assert extractor.config == custom_config
        assert extractor.config["title_selectors"] == [".custom-title"]
        assert extractor.config["min_content_length"] == 100
