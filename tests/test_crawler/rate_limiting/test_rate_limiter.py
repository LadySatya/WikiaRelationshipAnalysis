"""
Tests for RateLimiter class.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.crawler.rate_limiting.rate_limiter import RateLimiter


class TestRateLimiterInit:
    """Test RateLimiter initialization."""
    
    def test_init_with_default_parameters(self):
        """Test initialization with default parameters."""
        rate_limiter = RateLimiter()
        
        # Should initialize with default values
        assert hasattr(rate_limiter, 'default_delay')
        assert hasattr(rate_limiter, 'requests_per_minute')
        assert rate_limiter.default_delay == 1.0
        assert rate_limiter.requests_per_minute == 60
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        rate_limiter = RateLimiter(default_delay=2.5, requests_per_minute=30)
        
        assert rate_limiter.default_delay == 2.5
        assert rate_limiter.requests_per_minute == 30
    
    def test_init_with_invalid_delay(self):
        """Test initialization with invalid delay (negative/zero)."""
        # Should raise ValueError for negative delay
        with pytest.raises(ValueError, match="delay must be positive"):
            RateLimiter(default_delay=-1.0)
        
        # Should raise ValueError for zero delay
        with pytest.raises(ValueError, match="delay must be positive"):
            RateLimiter(default_delay=0.0)
    
    def test_init_with_invalid_rate_limit(self):
        """Test initialization with invalid rate limit (negative/zero)."""
        # Should raise ValueError for negative rate limit
        with pytest.raises(ValueError, match="requests_per_minute must be positive"):
            RateLimiter(requests_per_minute=-1)
        
        # Should raise ValueError for zero rate limit
        with pytest.raises(ValueError, match="requests_per_minute must be positive"):
            RateLimiter(requests_per_minute=0)
    
    def test_init_stores_parameters_correctly(self):
        """Test that initialization stores parameters correctly."""
        rate_limiter = RateLimiter(default_delay=3.0, requests_per_minute=120)
        
        # Should initialize domain tracking data structures
        assert hasattr(rate_limiter, '_domain_delays')
        assert hasattr(rate_limiter, '_domain_requests')
        assert hasattr(rate_limiter, '_domain_rate_limits')
        assert isinstance(rate_limiter._domain_delays, dict)
        assert isinstance(rate_limiter._domain_requests, dict)
        assert isinstance(rate_limiter._domain_rate_limits, dict)


class TestRateLimiterWaitIfNeeded:
    """Test RateLimiter.wait_if_needed method."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter(default_delay=1.0, requests_per_minute=60)
    
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
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_subsequent_request_waits(self, rate_limiter):
        """Test subsequent request waits for proper delay."""
        url = "https://example.com/page1"

        # First request - no wait
        await rate_limiter.wait_if_needed(url)
        rate_limiter.record_request(url)

        # Second request should wait for default delay
        start_time = time.time()
        await rate_limiter.wait_if_needed(url)
        elapsed = time.time() - start_time

        # Should wait approximately 1 second (±0.1s tolerance)
        assert 0.9 <= elapsed <= 1.1
    
    @pytest.mark.asyncio
    async def test_different_domains_independent(self, rate_limiter):
        """Test requests to different domains are independent."""
        url1 = "https://example.com/page1"
        url2 = "https://different.com/page1"
        
        # Make request to first domain and record it
        await rate_limiter.wait_if_needed(url1)
        rate_limiter.record_request(url1)
        
        # Request to different domain should not wait
        start_time = time.time()
        await rate_limiter.wait_if_needed(url2)
        elapsed = time.time() - start_time
        
        # Should complete immediately since it's a different domain
        assert elapsed < 0.1
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_requests_per_minute_enforcement(self, rate_limiter):
        """Test requests per minute limit is enforced."""
        # Create rate limiter with very low limit for testing
        test_limiter = RateLimiter(default_delay=0.1, requests_per_minute=2)
        url = "https://example.com/page1"

        # Make 2 requests quickly (should be allowed)
        await test_limiter.wait_if_needed(url)
        test_limiter.record_request(url)
        await asyncio.sleep(0.1)  # Small delay

        await test_limiter.wait_if_needed(url)
        test_limiter.record_request(url)

        # Third request should be rate limited (wait longer)
        start_time = time.time()
        await test_limiter.wait_if_needed(url)
        elapsed = time.time() - start_time

        # Should wait longer due to rate limiting
        assert elapsed > 0.5
    
    @pytest.mark.asyncio
    async def test_burst_protection(self, rate_limiter):
        """Test burst protection prevents too many rapid requests."""
        pass
    
    @pytest.mark.asyncio
    async def test_wait_accuracy(self, rate_limiter):
        """Test wait time is accurate within reasonable tolerance."""
        pass


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
    
    def test_set_domain_rate_limit(self, rate_limiter):
        """Test setting custom rate limit for specific domain."""
        domain = "example.com"
        custom_rate_limit = 30
        
        rate_limiter.set_domain_rate_limit(domain, custom_rate_limit)
        
        # Should store the custom rate limit for the domain
        assert domain in rate_limiter._domain_rate_limits
        assert rate_limiter._domain_rate_limits[domain] == custom_rate_limit
    
    def test_set_domain_rate_limit_invalid_values(self, rate_limiter):
        """Test setting invalid rate limit values raises errors."""
        pass
    
    @pytest.mark.asyncio
    async def test_domain_specific_delays_applied(self, rate_limiter):
        """Test domain-specific delays are applied correctly."""
        pass
    
    @pytest.mark.asyncio
    async def test_domain_specific_rate_limits_applied(self, rate_limiter):
        """Test domain-specific rate limits are applied correctly."""
        pass


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
        expected_keys = {
            'request_count', 'last_request_time', 'delay_seconds', 
            'requests_per_minute', 'current_requests_in_window'
        }
        assert isinstance(stats, dict)
        assert set(stats.keys()) == expected_keys
        assert stats['request_count'] == 0
        assert stats['last_request_time'] is None
    
    def test_get_domain_stats_after_requests(self, rate_limiter):
        """Test domain stats are updated after requests."""
        pass
    
    def test_record_request_updates_stats(self, rate_limiter):
        """Test record_request method updates domain statistics."""
        pass
    
    def test_stats_include_required_fields(self, rate_limiter):
        """Test domain stats include all required fields."""
        pass


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
    
    def test_is_rate_limited_true(self, rate_limiter):
        """Test rate limit detection when domain is rate limited."""
        pass
    
    def test_is_rate_limited_false(self, rate_limiter):
        """Test rate limit detection when domain is not rate limited."""
        pass
    
    def test_calculate_wait_time_no_previous_requests(self, rate_limiter):
        """Test wait time calculation for first request."""
        pass
    
    def test_calculate_wait_time_with_previous_requests(self, rate_limiter):
        """Test wait time calculation with request history."""
        pass
    
    def test_cleanup_old_requests(self, rate_limiter):
        """Test cleanup of old request timestamps."""
        pass
    
    def test_cleanup_preserves_recent_requests(self, rate_limiter):
        """Test cleanup preserves recent request timestamps."""
        pass


class TestRateLimiterConcurrency:
    """Test RateLimiter thread safety and concurrent access."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_same_domain(self, rate_limiter):
        """Test concurrent requests to same domain are properly queued."""
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_different_domains(self, rate_limiter):
        """Test concurrent requests to different domains don't interfere."""
        pass
    
    @pytest.mark.asyncio
    async def test_thread_safety_of_domain_stats(self, rate_limiter):
        """Test thread safety of domain statistics updates."""
        pass


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
    
    def test_domain_stats_invalid_domain(self, rate_limiter):
        """Test getting stats for invalid domain."""
        pass
    
    @pytest.mark.asyncio
    async def test_very_high_rate_limit(self, rate_limiter):
        """Test behavior with very high requests per minute."""
        pass
    
    @pytest.mark.asyncio
    async def test_very_low_rate_limit(self, rate_limiter):
        """Test behavior with very low requests per minute."""
        pass