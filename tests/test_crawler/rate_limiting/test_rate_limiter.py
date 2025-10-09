"""
Tests for RateLimiter class.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.crawler.rate_limiting.rate_limiter import RateLimiter

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


class TestRateLimiterInit:
    """Test RateLimiter initialization."""
    
    def test_init_with_default_parameters(self):
        """Test initialization with default parameters."""
        rate_limiter = RateLimiter()

        # Should initialize with default values
        assert hasattr(rate_limiter, 'default_delay')
        assert rate_limiter.default_delay == 1.0
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        rate_limiter = RateLimiter(default_delay=2.5)

        assert rate_limiter.default_delay == 2.5
    
    def test_init_with_invalid_delay(self):
        """Test initialization with invalid delay (negative/zero)."""
        # Should raise ValueError for negative delay
        with pytest.raises(ValueError, match="delay must be positive"):
            RateLimiter(default_delay=-1.0)
        
        # Should raise ValueError for zero delay
        with pytest.raises(ValueError, match="delay must be positive"):
            RateLimiter(default_delay=0.0)
    
    def test_init_stores_parameters_correctly(self):
        """Test that initialization stores parameters correctly."""
        rate_limiter = RateLimiter(default_delay=3.0)

        # Should initialize domain tracking data structures
        assert hasattr(rate_limiter, '_domain_delays')
        assert hasattr(rate_limiter, '_domain_requests')
        assert isinstance(rate_limiter._domain_delays, dict)
        assert isinstance(rate_limiter._domain_requests, dict)


class TestRateLimiterWaitIfNeeded:
    """Test RateLimiter.wait_if_needed method."""

    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter(default_delay=1.0)
    
    @pytest.mark.asyncio
    async def test_first_request_no_wait(self, rate_limiter):
        """Test first request to domain requires no wait."""
        url = "https://example.com/page1"
        
        # First request should not wait
        start_time = time.time()
        await rate_limiter.wait_if_needed(url)
        elapsed = time.time() - start_time
        
        # Should complete almost immediately (< 0.1 seconds)
        assert elapsed < 0.1
    
    @pytest.mark.asyncio
    async def test_second_request_waits_full_delay(self, rate_limiter):
        """Test second request to same domain waits full configured delay."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"

        # First request should not wait
        await rate_limiter.wait_if_needed(url1)

        # Second request to same domain should wait full delay
        start_time = time.time()
        await rate_limiter.wait_if_needed(url2)
        elapsed = time.time() - start_time

        # Should wait at least the configured delay (with small tolerance for execution time)
        assert elapsed >= rate_limiter.default_delay - 0.05
        # Should not wait excessively long (tolerance for system overhead)
        assert elapsed <= rate_limiter.default_delay + 0.2

    @pytest.mark.asyncio
    async def test_different_domains_independent(self, rate_limiter):
        """Test requests to different domains are independent."""
        url1 = "https://example.com/page1"
        url2 = "https://different.com/page1"

        # Make request to first domain
        await rate_limiter.wait_if_needed(url1)

        # Request to different domain should not wait (it's the first request to that domain)
        start_time = time.time()
        await rate_limiter.wait_if_needed(url2)
        elapsed = time.time() - start_time

        # Should complete immediately since it's a different domain
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_custom_domain_delay_applied(self, rate_limiter):
        """Test custom domain delay is applied correctly."""
        url = "https://custom.com/page1"
        custom_delay = 2.5

        # Set custom delay for domain
        rate_limiter.set_domain_delay("custom.com", custom_delay)

        # First request - no wait
        await rate_limiter.wait_if_needed(url)

        # Second request should use custom delay
        start_time = time.time()
        await rate_limiter.wait_if_needed(url)
        elapsed = time.time() - start_time

        # Should wait the custom delay
        assert elapsed >= custom_delay - 0.05
        assert elapsed <= custom_delay + 0.2


class TestRateLimiterDomainManagement:
    """Test RateLimiter domain-specific configuration."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()
    
    def test_set_domain_delay(self, rate_limiter):
        """Test setting custom delay for specific domain."""
        domain = "example.com"
        custom_delay = 2.5
        
        rate_limiter.set_domain_delay(domain, custom_delay)
        
        # Should store the custom delay for the domain
        assert domain in rate_limiter._domain_delays
        assert rate_limiter._domain_delays[domain] == custom_delay
    
    def test_set_domain_delay_invalid_values(self, rate_limiter):
        """Test setting invalid delay values raises errors."""
        domain = "example.com"
        
        # Should raise ValueError for negative delay
        with pytest.raises(ValueError, match="delay must be positive"):
            rate_limiter.set_domain_delay(domain, -1.0)
        
        # Should raise ValueError for zero delay
        with pytest.raises(ValueError, match="delay must be positive"):
            rate_limiter.set_domain_delay(domain, 0.0)
    


class TestRateLimiterDomainStats:
    """Test RateLimiter domain statistics and tracking."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()
    
    def test_get_domain_stats_new_domain(self, rate_limiter):
        """Test getting stats for new domain returns expected structure."""
        domain = "newdomain.com"
        stats = rate_limiter.get_domain_stats(domain)

        # Should return stats structure for new domain
        expected_keys = {'request_count', 'last_request_time', 'delay_seconds'}
        assert isinstance(stats, dict)
        assert set(stats.keys()) == expected_keys
        assert stats['request_count'] == 0
        assert stats['last_request_time'] is None
        assert stats['delay_seconds'] == rate_limiter.default_delay

    def test_get_domain_stats_after_requests(self, rate_limiter):
        """Test domain stats are updated after requests."""
        url = "https://example.com/page1"

        # Record a request
        rate_limiter.record_request(url)

        # Get stats for the domain
        stats = rate_limiter.get_domain_stats("example.com")

        # Should show updated stats
        assert stats['request_count'] == 1
        assert stats['last_request_time'] is not None
        assert isinstance(stats['last_request_time'], float)

    def test_record_request_updates_stats(self, rate_limiter):
        """Test record_request method updates domain statistics."""
        url = "https://example.com/page1"

        # Record multiple requests
        rate_limiter.record_request(url)
        rate_limiter.record_request(url)
        rate_limiter.record_request(url)

        # Get stats
        stats = rate_limiter.get_domain_stats("example.com")

        # Should have recorded all requests
        assert stats['request_count'] == 3

    def test_stats_with_custom_delay(self, rate_limiter):
        """Test domain stats reflect custom delay settings."""
        domain = "custom.com"
        custom_delay = 3.5

        # Set custom delay
        rate_limiter.set_domain_delay(domain, custom_delay)

        # Get stats
        stats = rate_limiter.get_domain_stats(domain)

        # Should reflect custom delay
        assert stats['delay_seconds'] == custom_delay


class TestRateLimiterPrivateMethods:
    """Test RateLimiter private/utility methods."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()
    
    def test_get_domain_from_url(self, rate_limiter):
        """Test domain extraction from various URL formats."""
        test_cases = [
            ("https://example.com/path", "example.com"),
            ("http://subdomain.example.com/path", "subdomain.example.com"),
            ("https://example.com:8080/path", "example.com:8080"),
            ("https://example.com", "example.com"),
            ("http://localhost:3000/api", "localhost:3000"),
        ]
        
        for url, expected_domain in test_cases:
            actual_domain = rate_limiter._get_domain(url)
            assert actual_domain == expected_domain, f"Failed for URL: {url}"
    
    def test_get_domain_invalid_url(self, rate_limiter):
        """Test domain extraction from invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "",
            None,
            "ftp://example.com",  # unsupported protocol
            "://missing-scheme.com",
        ]

        for invalid_url in invalid_urls:
            with pytest.raises((ValueError, AttributeError)):
                rate_limiter._get_domain(invalid_url)


class TestRateLimiterConcurrency:
    """Test RateLimiter thread safety and concurrent access."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_different_domains(self, rate_limiter):
        """Test concurrent requests to different domains don't interfere."""
        urls = [
            "https://domain1.com/page",
            "https://domain2.com/page",
            "https://domain3.com/page",
        ]

        # Make concurrent requests to different domains (all first requests)
        start_time = time.time()
        await asyncio.gather(*[rate_limiter.wait_if_needed(url) for url in urls])
        elapsed = time.time() - start_time

        # Should complete quickly since they're all first requests to different domains
        assert elapsed < 0.3


class TestRateLimiterEdgeCases:
    """Test RateLimiter edge cases and error conditions."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()
    
    @pytest.mark.asyncio
    async def test_wait_if_needed_invalid_url(self, rate_limiter):
        """Test wait_if_needed with invalid URL."""
        invalid_url = "not-a-valid-url"
        
        # Should raise ValueError for invalid URL
        with pytest.raises(ValueError):
            await rate_limiter.wait_if_needed(invalid_url)
    
    @pytest.mark.asyncio
    async def test_wait_if_needed_empty_url(self, rate_limiter):
        """Test wait_if_needed with empty URL."""
        # Should raise ValueError for empty URL
        with pytest.raises(ValueError):
            await rate_limiter.wait_if_needed("")

        # Should raise ValueError for None URL
        with pytest.raises(ValueError):
            await rate_limiter.wait_if_needed(None)