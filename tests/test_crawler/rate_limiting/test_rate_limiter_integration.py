"""
Integration tests for RateLimiter class.

These tests perform actual timing operations with real delays.
They are separated from unit tests to keep unit test suite fast.
"""

import asyncio
import time

import pytest

from src.crawler.rate_limiting.rate_limiter import RateLimiter

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestRateLimiterTimingIntegration:
    """Integration tests for RateLimiter timing and delays."""

    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter(default_delay=1.0)

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_subsequent_request_waits_full_delay(self, rate_limiter):
        """Test subsequent request waits for full configured delay."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"

        # First request - no wait
        await rate_limiter.wait_if_needed(url1)

        # Second request should wait full default delay (1.0s)
        start_time = time.time()
        await rate_limiter.wait_if_needed(url2)
        elapsed = time.time() - start_time

        # Should wait approximately 1 second (±0.1s tolerance)
        assert 0.9 <= elapsed <= 1.1

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_multiple_requests_all_wait_full_delay(self, rate_limiter):
        """Test that all subsequent requests wait the full configured delay."""
        # Create rate limiter with short delay for testing
        test_limiter = RateLimiter(default_delay=0.5)
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        # First request - no wait
        start_time = time.time()
        await test_limiter.wait_if_needed(urls[0])
        first_elapsed = time.time() - start_time
        assert first_elapsed < 0.1  # Should be fast

        # Second request - should wait 0.5s
        start_time = time.time()
        await test_limiter.wait_if_needed(urls[1])
        second_elapsed = time.time() - start_time
        assert 0.4 <= second_elapsed <= 0.6

        # Third request - should also wait 0.5s
        start_time = time.time()
        await test_limiter.wait_if_needed(urls[2])
        third_elapsed = time.time() - start_time
        assert 0.4 <= third_elapsed <= 0.6

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_custom_domain_delay_applied(self, rate_limiter):
        """Test custom domain delay is correctly applied in real timing."""
        url = "https://custom.com/page1"
        custom_delay = 0.7

        # Set custom delay for domain
        rate_limiter.set_domain_delay("custom.com", custom_delay)

        # First request - no wait
        await rate_limiter.wait_if_needed(url)

        # Second request should use custom delay
        start_time = time.time()
        await rate_limiter.wait_if_needed(url)
        elapsed = time.time() - start_time

        # Should wait the custom delay (±0.1s tolerance)
        assert 0.6 <= elapsed <= 0.8
