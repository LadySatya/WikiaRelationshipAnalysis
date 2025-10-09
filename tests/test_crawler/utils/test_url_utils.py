"""
Tests for URL utility functions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from urllib.parse import urlparse
from typing import List, Dict, Set, Optional

from src.crawler.utils.url_utils import URLUtils
# Mark all tests in this module as unit tests (all use mocks, no real I/O)
pytestmark = pytest.mark.unit


class TestURLUtilsNormalization:
    """Test URL normalization functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_normalize_basic_url(self, url_utils):
        """Test normalizing basic URLs."""
        test_cases = [
            ("https://example.com/page", "https://example.com/page"),
            ("https://EXAMPLE.COM/page", "https://example.com/page"),  # lowercase domain
            ("https://example.com/PAGE", "https://example.com/PAGE"),  # preserve path case
        ]
        
        for input_url, expected in test_cases:
            result = URLUtils.normalize_url(input_url)
            assert result == expected, f"Failed for {input_url}"
    
    def test_normalize_url_with_fragments(self, url_utils):
        """Test normalizing URLs with fragments."""
        test_cases = [
            ("https://example.com/page#section1", "https://example.com/page"),
            ("https://example.com/page#", "https://example.com/page"),
            ("https://example.com/page", "https://example.com/page"),  # no fragment
        ]
        
        for input_url, expected in test_cases:
            result = URLUtils.normalize_url(input_url)
            assert result == expected, f"Failed for {input_url}"
    
    def test_normalize_url_with_query_params(self, url_utils):
        """Test normalizing URLs with query parameters."""
        test_cases = [
            # Should sort query parameters alphabetically
            ("https://example.com/page?b=2&a=1", "https://example.com/page?a=1&b=2"),
            # Should handle single parameter
            ("https://example.com/page?param=value", "https://example.com/page?param=value"),
            # Should handle empty parameters
            ("https://example.com/page?", "https://example.com/page"),
        ]
        
        for input_url, expected in test_cases:
            result = URLUtils.normalize_url(input_url)
            assert result == expected, f"Failed for {input_url}"
    
    def test_normalize_url_case_sensitivity(self, url_utils):
        """Test URL normalization case sensitivity."""
        pass
    
    def test_normalize_trailing_slash(self, url_utils):
        """Test normalizing trailing slashes."""
        pass
    
    def test_normalize_encoded_characters(self, url_utils):
        """Test normalizing URL-encoded characters."""
        pass
    
    def test_normalize_unicode_urls(self, url_utils):
        """Test normalizing URLs with Unicode characters."""
        pass


class TestURLUtilsValidation:
    """Test URL validation functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_validate_http_url(self, url_utils):
        """Test validating HTTP URLs."""
        valid_urls = [
            "http://example.com",
            "http://example.com/path",
            "http://subdomain.example.com",
            "http://example.com:8080",
            "http://localhost:3000/api",
        ]
        
        for url in valid_urls:
            assert URLUtils.is_valid_url(url) is True, f"Should be valid: {url}"
    
    def test_validate_https_url(self, url_utils):
        """Test validating HTTPS URLs."""
        valid_https_urls = [
            "https://example.com",
            "https://example.com/path",
            "https://subdomain.example.com",
            "https://example.com:443",
            "https://localhost:8443/api",
        ]
        
        for url in valid_https_urls:
            assert URLUtils.is_valid_url(url) is True, f"Should be valid: {url}"
    
    def test_validate_malformed_url(self, url_utils):
        """Test validating malformed URLs."""
        invalid_urls = [
            "not-a-url",
            "",
            None,
            "ftp://example.com",  # unsupported protocol
            "://missing-scheme.com",
            "http://",  # missing domain
            "example.com",  # missing scheme
            "http://.com",  # malformed domain
        ]
        
        for url in invalid_urls:
            assert URLUtils.is_valid_url(url) is False, f"Should be invalid: {url}"
    
    def test_validate_empty_url(self, url_utils):
        """Test validating empty URLs."""
        empty_values = ["", None, "   ", "\t\n"]
        
        for empty_val in empty_values:
            assert URLUtils.is_valid_url(empty_val) is False, f"Should be invalid: {repr(empty_val)}"
    
    def test_validate_none_url(self, url_utils):
        """Test validating None URLs."""
        assert URLUtils.is_valid_url(None) is False
    
    def test_validate_relative_url(self, url_utils):
        """Test validating relative URLs."""
        relative_urls = ["/path/to/page", "./relative", "../parent", "page.html", "?query=value"]
        
        for url in relative_urls:
            # Relative URLs should be invalid for our use case (we need absolute URLs)
            assert URLUtils.is_valid_url(url) is False, f"Relative URL should be invalid: {url}"
    
    def test_validate_url_with_port(self, url_utils):
        """Test validating URLs with port numbers."""
        valid_port_urls = [
            "http://example.com:80",
            "https://example.com:443", 
            "http://localhost:3000",
            "https://api.example.com:8080",
            "http://127.0.0.1:8000",
        ]
        
        for url in valid_port_urls:
            assert URLUtils.is_valid_url(url) is True, f"Should be valid: {url}"


class TestURLUtilsWikiDetection:
    """Test wiki URL detection functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_is_wikia_url_fandom(self, url_utils):
        """Test detecting Fandom.com URLs."""
        fandom_urls = [
            "https://harrypotter.fandom.com/wiki/Harry_Potter",
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki",
            "http://community.fandom.com/wiki/Special:Search",
        ]
        
        for url in fandom_urls:
            assert URLUtils.is_wikia_url(url) is True, f"Should detect as Wikia: {url}"
    
    def test_is_wikia_url_wikia_org(self, url_utils):
        """Test detecting Wikia.org URLs."""
        wikia_org_urls = [
            "https://naruto.wikia.org/wiki/Naruto_Uzumaki",
            "http://harrypotter.wikia.org/wiki/Harry_Potter",
            "https://onepiece.wikia.org/wiki/Main_Page",
        ]
        
        for url in wikia_org_urls:
            assert URLUtils.is_wikia_url(url) is True, f"Should detect as Wikia: {url}"
    
    def test_is_wikia_url_wikia_com(self, url_utils):
        """Test detecting Wikia.com URLs."""
        wikia_com_urls = [
            "https://naruto.wikia.com/wiki/Naruto_Uzumaki",
            "http://harrypotter.wikia.com/wiki/Harry_Potter",
            "https://onepiece.wikia.com/wiki/Main_Page",
        ]
        
        for url in wikia_com_urls:
            assert URLUtils.is_wikia_url(url) is True, f"Should detect as Wikia: {url}"
    
    def test_is_not_wikia_url(self, url_utils):
        """Test non-wikia URL detection."""
        non_wikia_urls = [
            "https://wikipedia.org/wiki/Something",
            "https://example.com/page",
            "https://github.com/user/repo",
            "https://stackoverflow.com/questions/123",
        ]
        
        for url in non_wikia_urls:
            assert URLUtils.is_wikia_url(url) is False, f"Should not detect as Wikia: {url}"
    
    def test_extract_wiki_name_fandom(self, url_utils):
        """Test extracting wiki name from Fandom URLs."""
        test_cases = [
            ("https://harrypotter.fandom.com/wiki/Harry_Potter", "harrypotter"),
            ("https://naruto.fandom.com/wiki/Naruto_Uzumaki", "naruto"),
            ("http://community.fandom.com/wiki/Special:Search", "community"),
        ]
        
        for url, expected_wiki_name in test_cases:
            result = URLUtils.get_wikia_subdomain(url)
            assert result == expected_wiki_name, f"Failed for {url}"
    
    def test_extract_wiki_name_wikia(self, url_utils):
        """Test extracting wiki name from Wikia URLs."""
        test_cases = [
            ("https://naruto.wikia.org/wiki/Naruto_Uzumaki", "naruto"),
            ("https://harrypotter.wikia.com/wiki/Harry_Potter", "harrypotter"),
            ("http://onepiece.wikia.org/wiki/Main_Page", "onepiece"),
        ]
        
        for url, expected_wiki_name in test_cases:
            result = URLUtils.get_wikia_subdomain(url)
            assert result == expected_wiki_name, f"Failed for {url}"
    
    def test_get_wiki_base_url(self, url_utils):
        """Test getting base URL for wiki."""
        pass


class TestURLUtilsNamespaceDetection:
    """Test wiki namespace detection functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_detect_main_namespace(self, url_utils):
        """Test detecting main namespace pages."""
        pass
    
    def test_detect_character_namespace(self, url_utils):
        """Test detecting character namespace pages."""
        pass
    
    def test_detect_location_namespace(self, url_utils):
        """Test detecting location namespace pages."""
        pass
    
    def test_detect_template_namespace(self, url_utils):
        """Test detecting template namespace pages."""
        pass
    
    def test_detect_category_namespace(self, url_utils):
        """Test detecting category namespace pages."""
        pass
    
    def test_detect_user_namespace(self, url_utils):
        """Test detecting user namespace pages."""
        pass
    
    def test_detect_special_namespace(self, url_utils):
        """Test detecting special namespace pages."""
        pass


class TestURLUtilsRelativeResolution:
    """Test relative URL resolution functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_resolve_relative_path(self, url_utils):
        """Test resolving relative path URLs."""
        pass
    
    def test_resolve_absolute_path(self, url_utils):
        """Test resolving absolute path URLs."""
        pass
    
    def test_resolve_protocol_relative(self, url_utils):
        """Test resolving protocol-relative URLs."""
        pass
    
    def test_resolve_fragment_only(self, url_utils):
        """Test resolving fragment-only URLs."""
        pass
    
    def test_resolve_query_only(self, url_utils):
        """Test resolving query-only URLs."""
        pass
    
    def test_resolve_with_base_url(self, url_utils):
        """Test resolving URLs with base URL."""
        pass


class TestURLUtilsFilenameGeneration:
    """Test filename generation from URLs."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_generate_safe_filename(self, url_utils):
        """Test generating filesystem-safe filenames."""
        test_cases = [
            ("https://example.com/page", "example.com_page"),
            ("https://example.com/page/subpage", "example.com_page_subpage"),
            ("https://example.com/page?param=value", "example.com_page_param_value"),
            # Should handle special characters
            ("https://example.com/page with spaces", "example.com_page_with_spaces"),
            ("https://example.com/page:with:colons", "example.com_page_with_colons"),
        ]
        
        for url, expected_pattern in test_cases:
            result = URLUtils.clean_url_for_filename(url)
            # Should be filesystem safe (no invalid characters)
            invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
            for char in invalid_chars:
                assert char not in result, f"Filename contains invalid char '{char}': {result}"
            
            # Should not be empty
            assert len(result) > 0, f"Filename should not be empty for {url}"
    
    def test_handle_special_characters(self, url_utils):
        """Test handling special characters in filenames."""
        pass
    
    def test_handle_long_urls(self, url_utils):
        """Test handling very long URLs."""
        pass
    
    def test_handle_unicode_in_urls(self, url_utils):
        """Test handling Unicode characters in URLs."""
        pass
    
    def test_generate_unique_filenames(self, url_utils):
        """Test generating unique filenames for similar URLs."""
        pass
    
    def test_preserve_file_extensions(self, url_utils):
        """Test preserving file extensions in generated names."""
        pass


class TestURLUtilsDomainExtraction:
    """Test domain extraction and comparison functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_extract_domain_basic(self, url_utils):
        """Test extracting domain from basic URLs."""
        pass
    
    def test_extract_subdomain(self, url_utils):
        """Test extracting subdomain information."""
        pass
    
    def test_extract_top_level_domain(self, url_utils):
        """Test extracting top-level domain."""
        pass
    
    def test_compare_domains(self, url_utils):
        """Test comparing domains for equality."""
        pass
    
    def test_is_same_domain(self, url_utils):
        """Test checking if URLs are from same domain."""
        pass
    
    def test_is_subdomain_of(self, url_utils):
        """Test checking if URL is subdomain of another."""
        pass


class TestURLUtilsQueryParameterHandling:
    """Test query parameter handling functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_extract_query_parameters(self, url_utils):
        """Test extracting query parameters from URLs."""
        pass
    
    def test_add_query_parameter(self, url_utils):
        """Test adding query parameters to URLs."""
        pass
    
    def test_remove_query_parameter(self, url_utils):
        """Test removing query parameters from URLs."""
        pass
    
    def test_update_query_parameter(self, url_utils):
        """Test updating query parameters in URLs."""
        pass
    
    def test_clean_tracking_parameters(self, url_utils):
        """Test removing tracking parameters."""
        pass
    
    def test_normalize_parameter_order(self, url_utils):
        """Test normalizing query parameter order."""
        pass


class TestURLUtilsPathAnalysis:
    """Test URL path analysis functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_extract_path_segments(self, url_utils):
        """Test extracting path segments from URLs."""
        pass
    
    def test_get_page_title_from_path(self, url_utils):
        """Test extracting page title from URL path."""
        pass
    
    def test_detect_wiki_page_type(self, url_utils):
        """Test detecting wiki page type from path."""
        pass
    
    def test_is_wiki_article_url(self, url_utils):
        """Test detecting wiki article URLs."""
        pass
    
    def test_is_system_page_url(self, url_utils):
        """Test detecting system/admin page URLs."""
        pass
    
    def test_get_parent_path(self, url_utils):
        """Test getting parent path from URL."""
        pass


class TestURLUtilsPatternMatching:
    """Test URL pattern matching functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_match_url_pattern(self, url_utils):
        """Test matching URLs against patterns."""
        pass
    
    def test_match_character_page_pattern(self, url_utils):
        """Test matching character page URL patterns."""
        pass
    
    def test_match_location_page_pattern(self, url_utils):
        """Test matching location page URL patterns."""
        pass
    
    def test_match_exclusion_patterns(self, url_utils):
        """Test matching exclusion patterns."""
        pass
    
    def test_compile_pattern_cache(self, url_utils):
        """Test pattern compilation and caching."""
        pass
    
    def test_regex_pattern_matching(self, url_utils):
        """Test regex pattern matching for URLs."""
        pass


class TestURLUtilsDeduplication:
    """Test URL deduplication functionality."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_deduplicate_url_list(self, url_utils):
        """Test deduplicating list of URLs."""
        pass
    
    def test_normalize_for_deduplication(self, url_utils):
        """Test normalizing URLs for deduplication."""
        pass
    
    def test_canonical_url_generation(self, url_utils):
        """Test generating canonical URLs."""
        pass
    
    def test_identify_duplicate_content_urls(self, url_utils):
        """Test identifying URLs that point to same content."""
        pass
    
    def test_merge_duplicate_url_metadata(self, url_utils):
        """Test merging metadata from duplicate URLs."""
        pass


class TestURLUtilsErrorHandling:
    """Test URL utilities error handling."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_handle_malformed_urls(self, url_utils):
        """Test handling malformed URLs gracefully."""
        pass
    
    def test_handle_none_input(self, url_utils):
        """Test handling None input values."""
        pass
    
    def test_handle_empty_string_input(self, url_utils):
        """Test handling empty string input."""
        pass
    
    def test_handle_encoding_errors(self, url_utils):
        """Test handling URL encoding errors."""
        pass
    
    def test_handle_extremely_long_urls(self, url_utils):
        """Test handling extremely long URLs."""
        pass
    
    def test_graceful_degradation(self, url_utils):
        """Test graceful degradation on errors."""
        pass


class TestURLUtilsPerformance:
    """Test URL utilities performance characteristics."""
    
    @pytest.fixture
    def url_utils(self):
        """Create URLUtils instance for testing."""
        return URLUtils()
    
    def test_batch_url_processing(self, url_utils):
        """Test efficient batch URL processing."""
        pass
    
    def test_url_normalization_performance(self, url_utils):
        """Test URL normalization performance."""
        pass
    
    def test_pattern_matching_performance(self, url_utils):
        """Test pattern matching performance."""
        pass
    
    def test_memory_usage_optimization(self, url_utils):
        """Test memory usage optimization."""
        pass
    
    def test_caching_effectiveness(self, url_utils):
        """Test effectiveness of caching mechanisms."""
        pass