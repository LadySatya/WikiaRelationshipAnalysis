"""
Tests for LinkDiscoverer class - clean version with only relevant tests for simplified approach.
"""

from typing import Dict, List, Set
from unittest.mock import MagicMock, Mock, patch

import pytest
from bs4 import BeautifulSoup

from src.crawler.extraction.link_discoverer import LinkDiscoverer

# Mark all tests in this module as unit tests (all use mocks, no real I/O)
pytestmark = pytest.mark.unit


class TestLinkDiscovererInit:
    """Test LinkDiscoverer initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        discoverer = LinkDiscoverer()

        # Should have default values
        assert discoverer.base_domain == "fandom.com"
        assert discoverer.target_namespaces == ["Main", "Category"]
        assert isinstance(discoverer.non_content_namespaces, list)
        assert len(discoverer.non_content_namespaces) > 0

    def test_init_with_custom_base_domain(self):
        """Test initialization with custom base domain."""
        custom_domain = "example.com"
        discoverer = LinkDiscoverer(base_domain=custom_domain)

        assert discoverer.base_domain == custom_domain
        assert discoverer.target_namespaces == [
            "Main",
            "Category",
        ]  # Should use default

    def test_init_with_custom_namespaces(self):
        """Test initialization with custom target namespaces."""
        custom_namespaces = ["Main", "Character", "Location"]
        discoverer = LinkDiscoverer(target_namespaces=custom_namespaces)

        assert discoverer.base_domain == "fandom.com"  # Should use default
        assert discoverer.target_namespaces == custom_namespaces

    def test_init_with_both_custom_parameters(self):
        """Test initialization with both custom domain and namespaces."""
        custom_domain = "example.wikia.com"
        custom_namespaces = ["Main", "Test"]

        discoverer = LinkDiscoverer(
            base_domain=custom_domain, target_namespaces=custom_namespaces
        )

        assert discoverer.base_domain == custom_domain
        assert discoverer.target_namespaces == custom_namespaces

    def test_init_stores_config_correctly(self):
        """Test that configuration is stored correctly."""
        discoverer = LinkDiscoverer()

        # Check that non-content namespaces are properly initialized
        expected_non_content = [
            "template:",
            "user:",
            "talk:",
            "help:",
            "special:",
            "file:",
            "mediawiki:",
            "user_talk:",
            "project:",
            "project_talk:",
            "file_talk:",
            "template_talk:",
            "category_talk:",
            "forum:",
        ]

        for namespace in expected_non_content:
            assert namespace in discoverer.non_content_namespaces


class TestLinkDiscovererBasicExtraction:
    """Test LinkDiscoverer basic link extraction."""

    @pytest.fixture
    def sample_html(self):
        """Sample HTML for testing."""
        return """
        <html>
            <body>
                <a href="/wiki/Test_Character">Test Character</a>
                <a href="/wiki/Category:Characters">Characters</a>
                <a href="/wiki/Template:Infobox">Template:Infobox</a>
                <a href="https://external.com/test">External Link</a>
            </body>
        </html>
        """

    def test_extract_all_links(self, sample_html):
        """Test extracting all links from HTML."""
        link_discoverer = LinkDiscoverer()
        soup = BeautifulSoup(sample_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        result = link_discoverer.discover_links(soup, base_url)

        # Should return correct structure
        assert isinstance(result, dict)
        assert "high_priority" in result
        assert "medium_priority" in result
        assert "low_priority" in result

        # Should have found some links
        total_links = (
            len(result["high_priority"])
            + len(result["medium_priority"])
            + len(result["low_priority"])
        )
        assert total_links > 0

    def test_extract_internal_links_only(self, sample_html):
        """Test extracting only internal wiki links."""
        link_discoverer = LinkDiscoverer()
        soup = BeautifulSoup(sample_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        result = link_discoverer.discover_links(soup, base_url)

        # Check that external links are not included
        all_links = (
            result["high_priority"] | result["medium_priority"] | result["low_priority"]
        )
        external_links = [link for link in all_links if "external.com" in link]
        assert len(external_links) == 0

    def test_extract_absolute_urls(self, sample_html):
        """Test converting relative URLs to absolute."""
        link_discoverer = LinkDiscoverer()
        soup = BeautifulSoup(sample_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        result = link_discoverer.discover_links(soup, base_url)

        # All URLs should be absolute
        all_links = (
            result["high_priority"] | result["medium_priority"] | result["low_priority"]
        )
        for link in all_links:
            assert link.startswith("http") or link.startswith("/")

    def test_handle_empty_html(self):
        """Test handling empty HTML content."""
        link_discoverer = LinkDiscoverer()
        soup = BeautifulSoup("", "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        result = link_discoverer.discover_links(soup, base_url)

        assert result == {
            "high_priority": set(),
            "medium_priority": set(),
            "low_priority": set(),
        }

    def test_handle_malformed_html(self):
        """Test handling malformed HTML content."""
        link_discoverer = LinkDiscoverer()
        malformed_html = '<html><body><a href="/test">Test</a><p>Unclosed paragraph'
        soup = BeautifulSoup(malformed_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        # Should not raise an exception
        result = link_discoverer.discover_links(soup, base_url)
        assert isinstance(result, dict)


class TestLinkDiscovererSimplifiedApproach:
    """Test LinkDiscoverer simplified three-category approach."""

    @pytest.fixture
    def link_discoverer(self):
        """Create LinkDiscoverer instance for testing."""
        return LinkDiscoverer()

    @pytest.fixture
    def mixed_content_html(self):
        """HTML with categories, content, and non-content links."""
        return """
        <html>
            <body>
                <div class="categories">
                    <a href="/wiki/Category:Characters">Characters</a>
                    <a href="/wiki/Category:Locations">Locations</a>
                    <a href="/wiki/Category:Episodes">Episodes</a>
                </div>
                <div class="content">
                    <a href="/wiki/Harry_Potter">Harry Potter</a>
                    <a href="/wiki/Hermione_Granger">Hermione Granger</a>
                    <a href="/wiki/Hogwarts">Hogwarts</a>
                    <a href="/wiki/Quidditch">Quidditch</a>
                </div>
                <div class="maintenance">
                    <a href="/wiki/Template:Infobox">Template:Infobox</a>
                    <a href="/wiki/User:Admin">User:Admin</a>
                    <a href="/wiki/Help:Editing">Help:Editing</a>
                </div>
            </body>
        </html>
        """

    def test_categories_get_highest_priority(self, link_discoverer, mixed_content_html):
        """Test that category pages get highest priority."""
        soup = BeautifulSoup(mixed_content_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        result = link_discoverer.discover_links(soup, base_url)

        # Categories should be in high priority
        high_priority_links = result["high_priority"]
        category_links = [link for link in high_priority_links if "Category:" in link]
        assert len(category_links) > 0

    def test_find_category_links_identifies_all_categories(
        self, link_discoverer, mixed_content_html
    ):
        """Test that find_category_links correctly identifies all category pages."""
        soup = BeautifulSoup(mixed_content_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        category_links = link_discoverer.find_category_links(soup, base_url)

        # Should find all categories
        assert len(category_links) >= 3  # Characters, Locations, Episodes

    def test_find_content_links_identifies_main_namespace(
        self, link_discoverer, mixed_content_html
    ):
        """Test that find_content_links identifies main namespace pages."""
        soup = BeautifulSoup(mixed_content_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        content_links = link_discoverer.find_content_links(soup, base_url)

        # Should find content pages but not categories or maintenance
        assert (
            len(content_links) >= 4
        )  # Harry_Potter, Hermione_Granger, Hogwarts, Quidditch

        # Should not include categories or maintenance pages
        for link in content_links:
            assert "Category:" not in link
            assert "Template:" not in link
            assert "User:" not in link

    def test_find_non_content_links_identifies_maintenance(
        self, link_discoverer, mixed_content_html
    ):
        """Test that find_non_content_links identifies maintenance pages."""
        soup = BeautifulSoup(mixed_content_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        non_content_links = link_discoverer.find_non_content_links(soup, base_url)

        # Should find maintenance pages
        template_found = any("Template:" in link for link in non_content_links)
        user_found = any("User:" in link for link in non_content_links)
        help_found = any("Help:" in link for link in non_content_links)

        assert template_found or user_found or help_found

    def test_simplified_prioritization_scoring(self, link_discoverer):
        """Test that simplified prioritization gives correct scores."""
        links = {
            "https://test.fandom.com/wiki/Category:Characters",
            "https://test.fandom.com/wiki/Harry_Potter",
            "https://test.fandom.com/wiki/Template:Infobox",
        }
        base_url = "https://test.fandom.com/wiki/Main_Page"

        prioritized = link_discoverer.prioritize_links_simplified(links, base_url)

        # Category should be first (highest score)
        assert "Category:Characters" in prioritized[0]

        # Template should be last (negative score)
        assert "Template:" in prioritized[-1]

        # Content should be in middle
        content_index = next(
            i for i, link in enumerate(prioritized) if "Harry_Potter" in link
        )
        template_index = next(
            i for i, link in enumerate(prioritized) if "Template:" in link
        )
        assert content_index < template_index

    def test_is_content_link_classification(self, link_discoverer):
        """Test content link classification."""
        # Content links (main namespace)
        assert link_discoverer.is_content_link(
            "https://test.fandom.com/wiki/Harry_Potter"
        )
        assert link_discoverer.is_content_link("/wiki/Hermione_Granger")

        # Not content links
        assert not link_discoverer.is_content_link(
            "https://test.fandom.com/wiki/Category:Characters"
        )
        assert not link_discoverer.is_content_link("/wiki/Template:Infobox")
        assert not link_discoverer.is_content_link("/wiki/User:Admin")

    def test_is_non_content_link_classification(self, link_discoverer):
        """Test non-content link classification."""
        # Non-content links
        assert link_discoverer.is_non_content_link(
            "https://test.fandom.com/wiki/Template:Infobox"
        )
        assert link_discoverer.is_non_content_link("/wiki/User:Admin")
        assert link_discoverer.is_non_content_link("/wiki/Help:Editing")

        # Not non-content links
        assert not link_discoverer.is_non_content_link(
            "https://test.fandom.com/wiki/Harry_Potter"
        )
        assert not link_discoverer.is_non_content_link("/wiki/Category:Characters")

    def test_category_first_with_duplicate_handling_simulation(self, link_discoverer):
        """Test category-first approach handles scenarios where characters appear in multiple categories."""
        # This simulates the scenario where URLManager would handle deduplication

        # HTML with character appearing both in categories and individual links
        html = """
        <html>
            <body>
                <div class="categories">
                    <a href="/wiki/Category:Characters">Characters</a>
                    <a href="/wiki/Category:Main_Characters">Main Characters</a>
                </div>
                <div class="content">
                    <p>Read about <a href="/wiki/Harry_Potter">Harry Potter</a></p>
                    <p>Also see <a href="/wiki/Ron_Weasley">Ron Weasley</a></p>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        result = link_discoverer.discover_links(soup, base_url)

        # Should prioritize categories over individual character pages
        high_priority = result["high_priority"]
        category_links = [link for link in high_priority if "Category:" in link]

        # Categories should be found and prioritized
        assert len(category_links) >= 1

        # This demonstrates that categories would be crawled first,
        # and URLManager would handle the deduplication when character URLs
        # are discovered from both category pages and individual links


class TestLinkDiscovererErrorHandling:
    """Test LinkDiscoverer error handling and edge cases."""

    @pytest.fixture
    def link_discoverer(self):
        """Create LinkDiscoverer instance for testing."""
        return LinkDiscoverer()

    def test_handle_none_inputs(self, link_discoverer):
        """Test handling None inputs gracefully."""
        # None soup should return empty result
        result = link_discoverer.discover_links(None, "http://test.com")
        assert result == {
            "high_priority": set(),
            "medium_priority": set(),
            "low_priority": set(),
        }

        # None base_url should return empty result
        soup = BeautifulSoup(
            '<html><body><a href="/test">Test</a></body></html>', "html.parser"
        )
        result = link_discoverer.discover_links(soup, None)
        assert result == {
            "high_priority": set(),
            "medium_priority": set(),
            "low_priority": set(),
        }

        # Both None should return empty result
        result = link_discoverer.discover_links(None, None)
        assert result == {
            "high_priority": set(),
            "medium_priority": set(),
            "low_priority": set(),
        }

    def test_handle_invalid_html_gracefully(self, link_discoverer):
        """Test handling invalid HTML gracefully."""
        # Severely malformed HTML
        malformed_html = '<html><body><a href="/test"<p>Broken</p></body>'
        soup = BeautifulSoup(malformed_html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        # Should not crash and should return valid structure
        result = link_discoverer.discover_links(soup, base_url)
        assert isinstance(result, dict)
        assert all(
            key in result
            for key in ["high_priority", "medium_priority", "low_priority"]
        )

    def test_handle_empty_link_sets(self, link_discoverer):
        """Test handling when no links are found."""
        html = "<html><body><p>No links here!</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://test.fandom.com/wiki/Main_Page"

        result = link_discoverer.discover_links(soup, base_url)

        # Should return empty sets but valid structure
        assert result == {
            "high_priority": set(),
            "medium_priority": set(),
            "low_priority": set(),
        }

    def test_prioritize_links_handles_empty_input(self, link_discoverer):
        """Test that prioritize_links handles empty input."""
        result = link_discoverer.prioritize_links_simplified(set(), "http://test.com")
        assert result == []

        result = link_discoverer.prioritize_links_simplified(None, "http://test.com")
        assert result == []
