"""
Integration tests for BackoffHandler class.

These tests perform actual timing operations with real delays.
They are separated from unit tests to keep unit test suite fast.
"""

import pytest
import asyncio
import time

from src.crawler.rate_limiting.backoff_handler import BackoffHandler

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestBackoffHandlerTimingIntegration:
    """Integration tests for BackoffHandler timing and delays."""

    @pytest.fixture
    def backoff_handler(self):
        """Create BackoffHandler instance for testing."""
        return BackoffHandler(base_delay=0.1, max_delay=2.0, max_retries=3)

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_full_retry_cycle(self, backoff_handler):
        """Test full retry cycle: failure -> backoff -> retry."""
        url = "https://example.com/page"

        # Simulate a full retry cycle
        backoff_handler.record_failure(url, 500)
        assert backoff_handler.get_failure_count(url) == 1
        assert backoff_handler.should_retry(url, 500, attempt=1) is True

        # Wait with backoff
        start_time = time.time()
        await backoff_handler.wait_with_backoff(url, 2)
        elapsed = time.time() - start_time
        assert elapsed > 0  # Should have waited

        # Another failure
        backoff_handler.record_failure(url, 503)
        assert backoff_handler.get_failure_count(url) == 2

        # Eventually success
        backoff_handler.record_success(url)
        assert backoff_handler.get_failure_count(url) == 0

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_multiple_domains_concurrent(self, backoff_handler):
        """Test concurrent backoff handling for multiple domains."""
        urls = ["https://example1.com/page", "https://example2.com/page", "https://example3.com/page"]

        # Record failures for all domains
        for url in urls:
            backoff_handler.record_failure(url, 500)

        # Test concurrent backoff waits
        async def wait_for_domain(url):
            start_time = time.time()
            await backoff_handler.wait_with_backoff(url, 2)
            return time.time() - start_time

        # Run concurrent waits
        tasks = [wait_for_domain(url) for url in urls]
        wait_times = await asyncio.gather(*tasks)

        # All should have waited (none should be 0)
        assert all(t > 0 for t in wait_times)

        # All domains should still have their failure counts
        for url in urls:
            assert backoff_handler.get_failure_count(url) == 1

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.timing
    async def test_actual_wait_integration(self):
        """Test actual wait behavior with tiny delays for integration verification."""
        # Create handler with very small delays for fast testing
        handler = BackoffHandler(base_delay=0.01, max_delay=0.05, max_retries=2)
        url = "https://example.com/page"

        # Test that actual waiting works (without mocking)
        start_time = time.time()
        await handler.wait_with_backoff(url, 2)
        elapsed = time.time() - start_time

        # Should have actually waited some small amount
        assert elapsed >= 0.005  # At least 5ms
        assert elapsed <= 0.1    # But not too long

        # Verify exponential behavior with real waits
        start2 = time.time()
        await handler.wait_with_backoff(url, 2)
        time2 = time.time() - start2

        start3 = time.time()
        await handler.wait_with_backoff(url, 3)
        time3 = time.time() - start3

        # Even with jitter, attempt 3 should generally take longer
        assert time3 >= time2 * 0.8  # Allow some jitter variation
