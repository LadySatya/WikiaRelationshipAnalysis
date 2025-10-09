"""
Integration tests for RateLimiter class.

These tests perform actual timing operations with real delays.
They are separated from unit tests to keep unit test suite fast.
"""

import pytest
import asyncio
import time

from src.crawler.rate_limiting.rate_limiter import RateLimiter

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestRateLimiterTimingIntegration:
    """Integration tests for RateLimiter timing and delays."""

    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter(default_delay=1.0, requests_per_minute=60)

    @pytest.mark.asyncio
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
