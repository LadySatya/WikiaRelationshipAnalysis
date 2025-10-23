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


class TestPageExtractorNamespaceDetection:
    """Test namespace extraction from Wikia URLs."""

    @pytest.fixture
    def page_extractor(self):
        """Create PageExtractor instance for testing."""
        return PageExtractor()

    def test_get_namespace_main_namespace(self, page_extractor):
        """Test detection of Main namespace from standard wiki URLs."""
        test_cases = [
            "https://avatar.fandom.com/wiki/Aang",
            "https://avatar.fandom.com/wiki/Bolin",
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki",
            "https://buffy.fandom.com/wiki/Buffy_Summers",
        ]

        for url in test_cases:
            namespace = page_extractor.get_namespace(url)
            assert namespace == "Main", f"Expected Main namespace for {url}"

    def test_get_namespace_character_namespace_explicit(self, page_extractor):
        """Test detection of Character namespace with explicit prefix."""
        test_cases = [
            "https://avatar.fandom.com/wiki/Character:Aang",
            "https://starwars.fandom.com/wiki/Characters:Luke_Skywalker",
        ]

        for url in test_cases:
            namespace = page_extractor.get_namespace(url)
            assert "character" in namespace.lower(), f"Expected Character namespace for {url}"

    def test_get_namespace_location_namespace(self, page_extractor):
        """Test detection of Location namespace."""
        test_cases = [
            "https://avatar.fandom.com/wiki/Location:Ba_Sing_Se",
            "https://starwars.fandom.com/wiki/Locations:Tatooine",
        ]

        for url in test_cases:
            namespace = page_extractor.get_namespace(url)
            assert "location" in namespace.lower(), f"Expected Location namespace for {url}"

    def test_get_namespace_excluded_pages_return_none(self, page_extractor):
        """Test that excluded pages (Template, User, etc.) return None."""
        excluded_urls = [
            "https://avatar.fandom.com/wiki/Template:Character_Infobox",
            "https://avatar.fandom.com/wiki/User:JohnDoe",
            "https://avatar.fandom.com/wiki/File:Aang.jpg",
            "https://avatar.fandom.com/wiki/Category:Characters",
            "https://avatar.fandom.com/wiki/Help:Editing",
            "https://avatar.fandom.com/wiki/Special:RecentChanges",
        ]

        for url in excluded_urls:
            namespace = page_extractor.get_namespace(url)
            assert namespace is None, f"Expected None for excluded URL {url}"

    def test_get_namespace_generic_namespace_prefix(self, page_extractor):
        """Test detection of generic namespace prefixes."""
        test_cases = [
            ("https://avatar.fandom.com/wiki/Event:Hundred_Year_War", "Event"),
            ("https://avatar.fandom.com/wiki/Organization:White_Lotus", "Organization"),
        ]

        for url, expected_namespace in test_cases:
            namespace = page_extractor.get_namespace(url)
            assert namespace == expected_namespace, f"Expected {expected_namespace} for {url}"

    def test_get_namespace_empty_url(self, page_extractor):
        """Test that empty URL returns None."""
        assert page_extractor.get_namespace("") is None
        assert page_extractor.get_namespace(None) is None

    def test_get_namespace_non_wiki_url(self, page_extractor):
        """Test that non-wiki URLs return None."""
        non_wiki_urls = [
            "https://avatar.fandom.com/",
            "https://avatar.fandom.com/f/p/12345",
            "https://twitter.com/avatar",
        ]

        for url in non_wiki_urls:
            namespace = page_extractor.get_namespace(url)
            assert namespace is None, f"Expected None for non-wiki URL {url}"


class TestPageExtractorPortableInfobox:
    """Test extraction of Fandom portable infoboxes."""

    @pytest.fixture
    def page_extractor(self):
        """Create PageExtractor instance for testing."""
        return PageExtractor()

    def test_extract_portable_infobox_basic(self, page_extractor):
        """Test extraction of basic portable infobox data."""
        html = """
        <html>
        <body>
            <aside class="portable-infobox">
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Species</h3>
                    <div class="pi-data-value">Human</div>
                </div>
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Affiliation</h3>
                    <div class="pi-data-value">Team Avatar</div>
                </div>
            </aside>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        infobox_data = page_extractor.extract_infobox_data(soup)

        assert "Species" in infobox_data
        assert infobox_data["Species"] == "Human"
        assert "Affiliation" in infobox_data
        assert infobox_data["Affiliation"] == "Team Avatar"

    def test_extract_portable_infobox_multiple_fields(self, page_extractor):
        """Test extraction with many character-specific fields."""
        html = """
        <html>
        <body>
            <aside class="portable-infobox">
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Gender</h3>
                    <div class="pi-data-value">Male</div>
                </div>
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Age</h3>
                    <div class="pi-data-value">112</div>
                </div>
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Abilities</h3>
                    <div class="pi-data-value">Airbending, Waterbending</div>
                </div>
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Weapon</h3>
                    <div class="pi-data-value">Staff</div>
                </div>
            </aside>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        infobox_data = page_extractor.extract_infobox_data(soup)

        assert len(infobox_data) == 4
        assert infobox_data["Gender"] == "Male"
        assert infobox_data["Age"] == "112"
        assert infobox_data["Abilities"] == "Airbending, Waterbending"
        assert infobox_data["Weapon"] == "Staff"

    def test_extract_infobox_fallback_to_wikipedia_style(self, page_extractor):
        """Test fallback to Wikipedia-style table infobox if no portable infobox."""
        html = """
        <html>
        <body>
            <table class="infobox">
                <tr>
                    <th>Species</th>
                    <td>Human</td>
                </tr>
                <tr>
                    <th>Gender</th>
                    <td>Male</td>
                </tr>
            </table>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        infobox_data = page_extractor.extract_infobox_data(soup)

        # Should still extract from Wikipedia-style infobox
        assert "Species" in infobox_data
        assert infobox_data["Species"] == "Human"
        assert "Gender" in infobox_data
        assert infobox_data["Gender"] == "Male"

    def test_extract_infobox_prefers_portable_over_table(self, page_extractor):
        """Test that portable infobox is preferred when both formats exist."""
        html = """
        <html>
        <body>
            <aside class="portable-infobox">
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Source</h3>
                    <div class="pi-data-value">Portable</div>
                </div>
            </aside>
            <table class="infobox">
                <tr>
                    <th>Source</th>
                    <td>Table</td>
                </tr>
            </table>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        infobox_data = page_extractor.extract_infobox_data(soup)

        # Should use portable infobox data
        assert infobox_data["Source"] == "Portable"

    def test_extract_infobox_empty_when_no_infobox(self, page_extractor):
        """Test that empty dict is returned when no infobox present."""
        html = """
        <html>
        <body>
            <p>This page has no infobox.</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        infobox_data = page_extractor.extract_infobox_data(soup)

        assert infobox_data == {}

    def test_extract_infobox_handles_empty_values(self, page_extractor):
        """Test that empty label/value pairs are skipped."""
        html = """
        <html>
        <body>
            <aside class="portable-infobox">
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">Valid</h3>
                    <div class="pi-data-value">Value</div>
                </div>
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label"></h3>
                    <div class="pi-data-value">No label</div>
                </div>
                <div class="pi-item pi-data">
                    <h3 class="pi-data-label">No value</h3>
                    <div class="pi-data-value"></div>
                </div>
            </aside>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        infobox_data = page_extractor.extract_infobox_data(soup)

        # Should only have the valid pair
        assert len(infobox_data) == 1
        assert infobox_data["Valid"] == "Value"


class TestPageExtractorContentWithNamespace:
    """Test that extract_content includes namespace in result."""

    @pytest.fixture
    def page_extractor(self):
        """Create PageExtractor instance for testing."""
        return PageExtractor()

    def test_extract_content_includes_namespace(self, page_extractor):
        """Test that extract_content result includes namespace field."""
        html = """
        <html>
        <head><title>Aang</title></head>
        <body>
            <h1>Aang</h1>
            <p>Aang is the Avatar.</p>
        </body>
        </html>
        """
        url = "https://avatar.fandom.com/wiki/Aang"

        result = page_extractor.extract_content(html, url)

        assert "namespace" in result
        assert result["namespace"] == "Main"

    def test_extract_content_namespace_character(self, page_extractor):
        """Test namespace extraction for Character: prefix."""
        html = "<html><body><p>Content</p></body></html>"
        url = "https://avatar.fandom.com/wiki/Character:Zuko"

        result = page_extractor.extract_content(html, url)

        assert "namespace" in result
        assert "character" in result["namespace"].lower()

    def test_extract_content_namespace_none_for_excluded(self, page_extractor):
        """Test that excluded pages have None namespace."""
        html = "<html><body><p>Template content</p></body></html>"
        url = "https://avatar.fandom.com/wiki/Template:Infobox"

        result = page_extractor.extract_content(html, url)

        assert "namespace" in result
        assert result["namespace"] is None
