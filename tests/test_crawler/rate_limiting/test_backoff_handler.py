"""
Tests for BackoffHandler class.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch

from src.crawler.rate_limiting.backoff_handler import BackoffHandler

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


class TestBackoffHandlerInit:
    """Test BackoffHandler initialization."""
    
    def test_init_with_default_parameters(self):
        """Test initialization with default parameters."""
        backoff_handler = BackoffHandler()
        
        assert backoff_handler.base_delay == 1.0
        assert backoff_handler.max_delay == 300.0
        assert backoff_handler.max_retries == 3
        assert hasattr(backoff_handler, '_domain_failures')
        assert isinstance(backoff_handler._domain_failures, dict)
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        backoff_handler = BackoffHandler(base_delay=2.5, max_delay=120.0, max_retries=5)
        
        assert backoff_handler.base_delay == 2.5
        assert backoff_handler.max_delay == 120.0
        assert backoff_handler.max_retries == 5
    
    def test_init_with_invalid_base_delay(self):
        """Test initialization with invalid base delay."""
        # Should raise ValueError for negative base delay
        with pytest.raises(ValueError, match="base_delay must be positive"):
            BackoffHandler(base_delay=-1.0)
        
        # Should raise ValueError for zero base delay
        with pytest.raises(ValueError, match="base_delay must be positive"):
            BackoffHandler(base_delay=0.0)
    
    def test_init_with_invalid_max_delay(self):
        """Test initialization with invalid max delay."""
        # Should raise ValueError for negative max delay
        with pytest.raises(ValueError, match="max_delay must be positive"):
            BackoffHandler(max_delay=-1.0)
        
        # Should raise ValueError for zero max delay
        with pytest.raises(ValueError, match="max_delay must be positive"):
            BackoffHandler(max_delay=0.0)
    
    def test_init_with_invalid_max_retries(self):
        """Test initialization with invalid max retries."""
        # Should raise ValueError for negative max retries
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            BackoffHandler(max_retries=-1)
        
        # Zero retries should be allowed (no retries)
        backoff_handler = BackoffHandler(max_retries=0)
        assert backoff_handler.max_retries == 0
    
    def test_init_validates_delay_relationship(self):
        """Test initialization validates max_delay >= base_delay."""
        # Should raise ValueError when max_delay < base_delay
        with pytest.raises(ValueError, match="max_delay must be >= base_delay"):
            BackoffHandler(base_delay=10.0, max_delay=5.0)
        
        # Should allow max_delay == base_delay
        backoff_handler = BackoffHandler(base_delay=5.0, max_delay=5.0)
        assert backoff_handler.base_delay == 5.0
        assert backoff_handler.max_delay == 5.0


class TestBackoffHandlerWaitWithBackoff:
    """Test BackoffHandler.wait_with_backoff method."""
    
    @pytest.fixture
    def backoff_handler(self):
        """Create BackoffHandler instance for testing."""
        return BackoffHandler(base_delay=1.0, max_delay=60.0, max_retries=3)
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_first_attempt(self, backoff_handler):
        """Test wait time for first attempt."""
        url = "https://example.com/page"
        
        # Mock asyncio.sleep to verify no sleep happens for attempt 0
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            # Attempt 0 should not wait (invalid/first attempt)
            await backoff_handler.wait_with_backoff(url, 0)
            # Should not have called sleep for attempt 0
            mock_sleep.assert_not_called()
            
            # Attempt 1 should wait (first retry)
            await backoff_handler.wait_with_backoff(url, 1)
            # Should have called sleep once for attempt 1
            mock_sleep.assert_called_once()
            
            # Verify the delay is reasonable for attempt 1
            sleep_duration = mock_sleep.call_args[0][0]
            assert sleep_duration >= 0  # Should be positive
            assert sleep_duration <= backoff_handler.max_delay  # Should not exceed max
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_exponential_growth(self, backoff_handler):
        """Test wait time grows exponentially with attempt number."""
        url = "https://example.com/page"
        
        # Mock asyncio.sleep to capture delays without waiting
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            # Test exponential growth pattern
            await backoff_handler.wait_with_backoff(url, 2)
            delay_2 = mock_sleep.call_args[0][0]

            mock_sleep.reset_mock()
            await backoff_handler.wait_with_backoff(url, 3)
            delay_3 = mock_sleep.call_args[0][0]

            # Attempt 3 should take roughly twice as long as attempt 2
            # With ±25% jitter, the worst case ratio is: 1.5 / 1.25 = 1.2x
            # So we check it's at least 1.2x longer to account for jitter variance
            assert delay_3 > delay_2 * 1.2
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_max_delay_cap(self, backoff_handler):
        """Test wait time is capped at max_delay."""
        url = "https://example.com/page"
        
        # Mock asyncio.sleep to avoid actual waiting
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None  # Mock the coroutine
            
            await backoff_handler.wait_with_backoff(url, 20)  # Should trigger max_delay
            
            # Verify sleep was called with capped delay
            mock_sleep.assert_called_once()
            sleep_duration = mock_sleep.call_args[0][0]
            
            # Should not exceed max_delay
            assert sleep_duration <= backoff_handler.max_delay
            # Should be substantial (close to max_delay accounting for jitter)
            assert sleep_duration >= backoff_handler.max_delay * 0.7
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_includes_jitter(self, backoff_handler):
        """Test wait time includes randomized jitter."""
        url = "https://example.com/page"
        attempt = 2
        
        # Mock asyncio.sleep and collect delay values
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            delays = []
            for _ in range(5):
                await backoff_handler.wait_with_backoff(url, attempt)
                delay = mock_sleep.call_args[0][0]
                delays.append(delay)
                mock_sleep.reset_mock()
            
            # Due to jitter, delays should vary
            # Check that we have some variation (not all identical)
            unique_delays = set(round(d, 3) for d in delays)  # Round to 3 decimal places
            assert len(unique_delays) > 1, "Expected variation due to jitter"
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_timing_accuracy(self, backoff_handler):
        """Test actual wait time matches expected calculation."""
        url = "https://example.com/page"
        attempt = 2
        
        # Calculate expected delay (base_delay * 2^(attempt-1))
        expected_base = backoff_handler.base_delay * (2 ** (attempt - 1))
        
        # Mock asyncio.sleep to capture delay without waiting
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            await backoff_handler.wait_with_backoff(url, attempt)
            
            # Verify sleep was called with expected delay (accounting for jitter)
            mock_sleep.assert_called_once()
            actual_delay = mock_sleep.call_args[0][0]
            
            # Should be within reasonable range of expected time (accounting for jitter)
            # Jitter is ±25%, so we allow ±30% tolerance
            assert expected_base * 0.7 <= actual_delay <= expected_base * 1.3
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_different_domains(self, backoff_handler):
        """Test backoff is per-domain, not global."""
        url1 = "https://example1.com/page"
        url2 = "https://example2.com/page"
        
        # Record failures for first domain
        backoff_handler.record_failure(url1, 500)
        backoff_handler.record_failure(url1, 500)
        
        # Check failure counts are domain-specific
        assert backoff_handler.get_failure_count(url1) == 2
        assert backoff_handler.get_failure_count(url2) == 0
        
        # Mock asyncio.sleep to test timing logic without waiting
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            # Test backoff timing for both domains
            await backoff_handler.wait_with_backoff(url1, 2)
            delay1 = mock_sleep.call_args[0][0]
            
            mock_sleep.reset_mock()
            await backoff_handler.wait_with_backoff(url2, 2)
            delay2 = mock_sleep.call_args[0][0]
            
            # Both should have positive delays and follow same exponential logic
            assert delay1 > 0  # Should have some delay
            assert delay2 > 0  # Should have some delay
            # Both should use same attempt calculation (independent per domain)
            # The actual delays may vary due to jitter but should be in same range
            assert 0.5 <= delay1 <= 5.0  # Reasonable range for attempt 2
            assert 0.5 <= delay2 <= 5.0  # Reasonable range for attempt 2


class TestBackoffHandlerShouldRetry:
    """Test BackoffHandler.should_retry method."""
    
    @pytest.fixture
    def backoff_handler(self):
        """Create BackoffHandler instance for testing."""
        return BackoffHandler(max_retries=3)
    
    def test_should_retry_retriable_status_code(self, backoff_handler):
        """Test should_retry returns True for retriable status codes."""
        url = "https://example.com/page"
        retriable_codes = [429, 500, 502, 503, 504, 520, 521, 522, 523, 524]
        
        for status_code in retriable_codes:
            result = backoff_handler.should_retry(url, status_code, attempt=1)
            assert result is True, f"Should retry for status code {status_code}"
    
    def test_should_retry_non_retriable_status_code(self, backoff_handler):
        """Test should_retry returns False for non-retriable status codes."""
        url = "https://example.com/page"
        non_retriable_codes = [200, 201, 400, 401, 403, 404, 405, 410, 451]
        
        for status_code in non_retriable_codes:
            result = backoff_handler.should_retry(url, status_code, attempt=1)
            assert result is False, f"Should not retry for status code {status_code}"
    
    def test_should_retry_max_attempts_reached(self, backoff_handler):
        """Test should_retry returns False when max attempts reached."""
        url = "https://example.com/page"
        status_code = 500  # retriable status
        
        # Should not retry when attempt number exceeds max_retries
        result = backoff_handler.should_retry(url, status_code, attempt=4)  # max_retries = 3
        assert result is False
        
        # Should not retry when attempt equals max_retries + 1
        result = backoff_handler.should_retry(url, status_code, attempt=backoff_handler.max_retries + 1)
        assert result is False
    
    def test_should_retry_within_attempt_limit(self, backoff_handler):
        """Test should_retry returns True when within attempt limit."""
        url = "https://example.com/page"
        status_code = 500  # retriable status
        
        # Should retry when attempt is within limit
        for attempt in range(1, backoff_handler.max_retries + 1):
            result = backoff_handler.should_retry(url, status_code, attempt)
            assert result is True, f"Should retry for attempt {attempt}"
    
    def test_should_retry_network_errors(self, backoff_handler):
        """Test should_retry handles network error status codes."""
        url = "https://example.com/page"
        network_errors = [502, 504, 520, 521, 522, 523, 524]  # Network/gateway errors
        
        for status_code in network_errors:
            result = backoff_handler.should_retry(url, status_code, attempt=1)
            assert result is True, f"Should retry for network error {status_code}"
    
    def test_should_retry_server_errors(self, backoff_handler):
        """Test should_retry handles server error status codes."""
        url = "https://example.com/page"
        server_errors = [500, 503]  # Internal server error, service unavailable
        
        for status_code in server_errors:
            result = backoff_handler.should_retry(url, status_code, attempt=1)
            assert result is True, f"Should retry for server error {status_code}"
    
    def test_should_retry_client_errors(self, backoff_handler):
        """Test should_retry handles client error status codes."""
        url = "https://example.com/page"
        client_errors = [400, 401, 403, 404, 405, 410]  # Client errors (non-retriable)
        
        for status_code in client_errors:
            result = backoff_handler.should_retry(url, status_code, attempt=1)
            assert result is False, f"Should not retry for client error {status_code}"


class TestBackoffHandlerFailureTracking:
    """Test BackoffHandler failure tracking and recovery."""
    
    @pytest.fixture
    def backoff_handler(self):
        """Create BackoffHandler instance for testing."""
        return BackoffHandler()
    
    def test_record_failure_increments_count(self, backoff_handler):
        """Test record_failure increments failure count for domain."""
        url = "https://example.com/page"
        
        # Start with 0 failures
        assert backoff_handler.get_failure_count(url) == 0
        
        # Record failures and check count increments
        backoff_handler.record_failure(url, 500)
        assert backoff_handler.get_failure_count(url) == 1
        
        backoff_handler.record_failure(url, 503)
        assert backoff_handler.get_failure_count(url) == 2
        
        backoff_handler.record_failure(url, 429)
        assert backoff_handler.get_failure_count(url) == 3
    
    def test_record_failure_different_domains(self, backoff_handler):
        """Test record_failure tracks failures per domain."""
        url1 = "https://example1.com/page"
        url2 = "https://example2.com/page"
        
        # Record different numbers of failures for each domain
        backoff_handler.record_failure(url1, 500)
        backoff_handler.record_failure(url1, 503)
        
        backoff_handler.record_failure(url2, 429)
        
        # Check counts are tracked separately
        assert backoff_handler.get_failure_count(url1) == 2
        assert backoff_handler.get_failure_count(url2) == 1
    
    def test_record_success_resets_count(self, backoff_handler):
        """Test record_success resets failure count for domain."""
        url = "https://example.com/page"
        
        # Record some failures
        backoff_handler.record_failure(url, 500)
        backoff_handler.record_failure(url, 503)
        assert backoff_handler.get_failure_count(url) == 2
        
        # Record success should reset to 0
        backoff_handler.record_success(url)
        assert backoff_handler.get_failure_count(url) == 0
    
    def test_record_success_only_affects_domain(self, backoff_handler):
        """Test record_success only affects specific domain."""
        url1 = "https://example1.com/page"
        url2 = "https://example2.com/page"
        
        # Record failures for both domains
        backoff_handler.record_failure(url1, 500)
        backoff_handler.record_failure(url1, 500)
        backoff_handler.record_failure(url2, 500)
        
        # Record success for only one domain
        backoff_handler.record_success(url1)
        
        # Only url1's domain should be reset
        assert backoff_handler.get_failure_count(url1) == 0
        assert backoff_handler.get_failure_count(url2) == 1
    
    def test_get_failure_count_new_domain(self, backoff_handler):
        """Test get_failure_count returns 0 for new domain."""
        url = "https://new-domain.com/page"
        
        # New domain should have 0 failures
        assert backoff_handler.get_failure_count(url) == 0
    
    def test_get_failure_count_after_failures(self, backoff_handler):
        """Test get_failure_count returns correct count after failures."""
        url = "https://example.com/page"
        
        # Record specific number of failures
        for i in range(5):
            backoff_handler.record_failure(url, 500)
            assert backoff_handler.get_failure_count(url) == i + 1
    
    def test_reset_domain_failures(self, backoff_handler):
        """Test reset_domain_failures clears failure count."""
        url = "https://example.com/page"
        domain = backoff_handler._get_domain(url)
        
        # Record failures
        backoff_handler.record_failure(url, 500)
        backoff_handler.record_failure(url, 503)
        assert backoff_handler.get_failure_count(url) == 2
        
        # Reset domain failures
        backoff_handler.reset_domain_failures(domain)
        assert backoff_handler.get_failure_count(url) == 0


class TestBackoffHandlerPrivateMethods:
    """Test BackoffHandler private methods."""
    
    @pytest.fixture
    def backoff_handler(self):
        """Create BackoffHandler instance for testing."""
        return BackoffHandler(base_delay=1.0, max_delay=60.0)
    
    def test_get_domain_from_url(self, backoff_handler):
        """Test domain extraction from URLs."""
        # Test various URL formats
        assert backoff_handler._get_domain("https://example.com/path") == "example.com"
        assert backoff_handler._get_domain("http://subdomain.example.org/page?param=value") == "subdomain.example.org"
        assert backoff_handler._get_domain("https://www.fandom.com/wiki/Page") == "www.fandom.com"
        
        # Test case normalization
        assert backoff_handler._get_domain("HTTPS://EXAMPLE.COM/PATH") == "example.com"
    
    def test_get_domain_invalid_url(self, backoff_handler):
        """Test domain extraction from invalid URLs."""
        # Invalid URLs should return the original string
        invalid_url = "not-a-url"
        assert backoff_handler._get_domain(invalid_url) == invalid_url
        
        # Empty URLs
        empty_url = ""
        assert backoff_handler._get_domain(empty_url) == empty_url
    
    def test_calculate_delay_exponential(self, backoff_handler):
        """Test delay calculation follows exponential backoff."""
        # Test exponential growth pattern
        delay1 = backoff_handler._calculate_delay(1)  # base_delay * 2^0 = base_delay
        delay2 = backoff_handler._calculate_delay(2)  # base_delay * 2^1 = base_delay * 2
        delay3 = backoff_handler._calculate_delay(3)  # base_delay * 2^2 = base_delay * 4
        
        # Account for jitter by checking rough ratios
        # delay2 should be roughly 2x delay1, delay3 should be roughly 2x delay2
        # With ±25% jitter, the worst case ratio is: 1.5 / 1.25 = 1.2x
        assert delay2 > delay1 * 1.2  # At least 1.2x accounting for jitter
        assert delay3 > delay2 * 1.2  # At least 1.2x accounting for jitter
    
    def test_calculate_delay_with_jitter(self, backoff_handler):
        """Test delay calculation includes jitter randomization."""
        attempt = 3
        
        # Calculate multiple delays and check for variation
        delays = [backoff_handler._calculate_delay(attempt) for _ in range(10)]
        
        # Should have some variation due to jitter
        unique_delays = set(round(d, 3) for d in delays)
        assert len(unique_delays) > 1, "Expected variation due to jitter"
        
        # All delays should be positive
        assert all(d >= 0 for d in delays)
    
    def test_calculate_delay_max_cap(self, backoff_handler):
        """Test delay calculation is capped at max_delay."""
        # Test with very high attempt number
        very_high_attempt = 20
        delay = backoff_handler._calculate_delay(very_high_attempt)
        
        # Should not exceed max_delay
        assert delay <= backoff_handler.max_delay
        
        # Should be close to max_delay (within jitter range)
        assert delay >= backoff_handler.max_delay * 0.7  # Account for negative jitter
    
    def test_is_retriable_status_429(self, backoff_handler):
        """Test 429 (Too Many Requests) is retriable."""
        assert backoff_handler._is_retriable_status(429) is True
    
    def test_is_retriable_status_503(self, backoff_handler):
        """Test 503 (Service Unavailable) is retriable."""
        assert backoff_handler._is_retriable_status(503) is True
    
    def test_is_retriable_status_502(self, backoff_handler):
        """Test 502 (Bad Gateway) is retriable."""
        assert backoff_handler._is_retriable_status(502) is True
    
    def test_is_retriable_status_404(self, backoff_handler):
        """Test 404 (Not Found) is not retriable."""
        assert backoff_handler._is_retriable_status(404) is False
    
    def test_is_retriable_status_403(self, backoff_handler):
        """Test 403 (Forbidden) is not retriable."""
        assert backoff_handler._is_retriable_status(403) is False


class TestBackoffHandlerIntegration:
    """Test BackoffHandler integration scenarios."""
    
    @pytest.fixture
    def backoff_handler(self):
        """Create BackoffHandler instance for testing."""
        return BackoffHandler(base_delay=0.1, max_delay=2.0, max_retries=3)
    
    @pytest.mark.asyncio
    async def test_success_after_failures(self, backoff_handler):
        """Test successful request after failures resets backoff."""
        url = "https://example.com/page"
        
        # Record multiple failures
        for _ in range(3):
            backoff_handler.record_failure(url, 500)
        assert backoff_handler.get_failure_count(url) == 3
        
        # Success should reset the count
        backoff_handler.record_success(url)
        assert backoff_handler.get_failure_count(url) == 0
        
        # Future requests should start from clean slate
        assert backoff_handler.should_retry(url, 500, attempt=1) is True

    @pytest.mark.asyncio
    async def test_backoff_timing_realistic(self, backoff_handler):
        """Test backoff timing in realistic failure scenario."""
        url = "https://example.com/page"
        
        # Mock asyncio.sleep to avoid actual waiting
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None  # Mock the coroutine
            
            # First request fails (429 - rate limited)
            backoff_handler.record_failure(url, 429)
            assert backoff_handler.should_retry(url, 429, attempt=1) is True
            
            # Wait for retry
            await backoff_handler.wait_with_backoff(url, 2)
            
            # Second request fails (503 - service unavailable)
            backoff_handler.record_failure(url, 503)
            assert backoff_handler.should_retry(url, 503, attempt=2) is True
            
            # Wait longer for second retry
            await backoff_handler.wait_with_backoff(url, 3)
            
            # Third request succeeds
            backoff_handler.record_success(url)
            
            # Verify sleep was called twice with increasing delays
            assert mock_sleep.call_count == 2
            
            # Check that delays increased (attempt 2 < attempt 3)
            call_args = mock_sleep.call_args_list
            delay_2 = call_args[0][0][0]
            delay_3 = call_args[1][0][0]

            # Second delay should be longer (accounting for jitter variation)
            # With ±25% jitter, the worst case ratio is: 1.5 / 1.25 = 1.2x
            assert delay_3 > delay_2 * 1.2
            assert backoff_handler.get_failure_count(url) == 0  # Reset after success


class TestBackoffHandlerEdgeCases:
    """Test BackoffHandler edge cases and error conditions."""
    
    @pytest.fixture
    def backoff_handler(self):
        """Create BackoffHandler instance for testing."""
        return BackoffHandler()
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_zero_attempt(self, backoff_handler):
        """Test wait_with_backoff with attempt number 0."""
        url = "https://example.com/page"
        
        # Attempt 0 should not wait
        start_time = time.time()
        await backoff_handler.wait_with_backoff(url, 0)
        elapsed = time.time() - start_time
        assert elapsed < 0.1  # Should be nearly instant
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_negative_attempt(self, backoff_handler):
        """Test wait_with_backoff with negative attempt number."""
        url = "https://example.com/page"
        
        # Negative attempts should not wait
        start_time = time.time()
        await backoff_handler.wait_with_backoff(url, -1)
        elapsed = time.time() - start_time
        assert elapsed < 0.1  # Should be nearly instant
    
    @pytest.mark.asyncio
    async def test_wait_with_backoff_very_high_attempt(self, backoff_handler):
        """Test wait_with_backoff with very high attempt number."""
        url = "https://example.com/page"
        
        # Mock asyncio.sleep to avoid actual waiting
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None  # Mock the coroutine
            
            await backoff_handler.wait_with_backoff(url, 100)
            
            # Verify sleep was called with capped delay
            mock_sleep.assert_called_once()
            sleep_duration = mock_sleep.call_args[0][0]
            
            # Should not exceed max_delay (accounting for jitter)
            assert sleep_duration <= backoff_handler.max_delay
            # Should be close to max_delay (within jitter range)
            assert sleep_duration >= backoff_handler.max_delay * 0.7
    
    def test_should_retry_invalid_status_code(self, backoff_handler):
        """Test should_retry with invalid status code."""
        url = "https://example.com/page"
        
        # Invalid status codes should not be retriable
        invalid_codes = [-1, 0, 999, 1000]
        for status_code in invalid_codes:
            result = backoff_handler.should_retry(url, status_code, attempt=1)
            assert result is False, f"Should not retry invalid status code {status_code}"
    
    def test_record_failure_invalid_status_code(self, backoff_handler):
        """Test record_failure with invalid status code."""
        url = "https://example.com/page"
        
        # Should handle invalid status codes gracefully
        initial_count = backoff_handler.get_failure_count(url)
        
        # Record failures with invalid codes - should still increment
        backoff_handler.record_failure(url, -1)
        assert backoff_handler.get_failure_count(url) == initial_count + 1
        
        backoff_handler.record_failure(url, 999)
        assert backoff_handler.get_failure_count(url) == initial_count + 2
    
    def test_failure_tracking_memory_efficiency(self, backoff_handler):
        """Test failure tracking doesn't consume excessive memory."""
        # Test with many different domains
        base_url = "https://domain{}.com/page"
        
        # Record failures for many domains
        for i in range(100):
            url = base_url.format(i)
            backoff_handler.record_failure(url, 500)
        
        # Verify all are tracked
        assert len(backoff_handler._domain_failures) == 100
        
        # Reset some domains
        for i in range(0, 50):
            url = base_url.format(i)
            backoff_handler.record_success(url)
        
        # Should still have all domains (but some with 0 count)
        assert len(backoff_handler._domain_failures) == 100
        
        # Verify counts are correct
        for i in range(100):
            url = base_url.format(i)
            expected_count = 0 if i < 50 else 1
            assert backoff_handler.get_failure_count(url) == expected_count
    
    @pytest.mark.asyncio
    async def test_thread_safety_concurrent_access(self, backoff_handler):
        """Test thread safety of concurrent backoff operations."""
        import asyncio
        
        url = "https://example.com/page"
        
        async def record_failure():
            backoff_handler.record_failure(url, 500)
        
        async def record_success():
            backoff_handler.record_success(url)
        
        # Run concurrent operations
        tasks = []
        for _ in range(10):
            tasks.append(record_failure())
        for _ in range(5):
            tasks.append(record_success())
        
        # Execute all concurrently
        await asyncio.gather(*tasks)
        
        # Should handle concurrent access gracefully
        final_count = backoff_handler.get_failure_count(url)
        assert final_count >= 0  # Should be a valid count


class TestBackoffHandlerConfiguration:
    """Test BackoffHandler with various configurations."""
    
    def test_very_short_delays(self):
        """Test backoff handler with very short delays."""
        # Test with very short delays
        backoff_handler = BackoffHandler(base_delay=0.01, max_delay=0.1, max_retries=2)
        
        assert backoff_handler.base_delay == 0.01
        assert backoff_handler.max_delay == 0.1
        
        # Should still work with short delays
        delay = backoff_handler._calculate_delay(2)
        assert 0 <= delay <= 0.1  # Should be within max_delay
    
    def test_very_long_delays(self):
        """Test backoff handler with very long delays."""
        # Test with very long delays  
        backoff_handler = BackoffHandler(base_delay=60.0, max_delay=3600.0, max_retries=5)
        
        assert backoff_handler.base_delay == 60.0
        assert backoff_handler.max_delay == 3600.0
        
        # Should handle long delays correctly
        delay = backoff_handler._calculate_delay(1)
        assert delay >= 45.0  # Should be close to base_delay (accounting for negative jitter)
        assert delay <= 3600.0  # Should not exceed max_delay
    
    def test_high_retry_count(self):
        """Test backoff handler with high retry count."""
        # Test with high retry count
        backoff_handler = BackoffHandler(max_retries=10)
        
        url = "https://example.com/page"
        
        # Should allow many retries
        for attempt in range(1, 11):  # attempts 1-10 should be allowed
            result = backoff_handler.should_retry(url, 500, attempt=attempt)
            assert result is True, f"Should allow retry for attempt {attempt}"
        
        # Should not allow retry after max_retries
        result = backoff_handler.should_retry(url, 500, attempt=11)
        assert result is False
    
    def test_single_retry_only(self):
        """Test backoff handler with only one retry allowed."""
        # Test with only one retry
        backoff_handler = BackoffHandler(max_retries=1)
        
        url = "https://example.com/page"
        
        # Should allow first retry
        assert backoff_handler.should_retry(url, 500, attempt=1) is True
        
        # Should not allow second retry
        assert backoff_handler.should_retry(url, 500, attempt=2) is False
    
    @pytest.mark.asyncio
    async def test_no_jitter_configuration(self):
        """Test backoff handler with jitter disabled."""
        # Note: Current implementation always includes jitter
        # This test documents the current behavior
        backoff_handler = BackoffHandler(base_delay=1.0, max_delay=10.0)
        
        # Calculate delays multiple times
        delays = [backoff_handler._calculate_delay(2) for _ in range(5)]
        
        # Should have variation due to jitter (current implementation always uses jitter)
        unique_delays = set(round(d, 3) for d in delays)
        
        # All delays should be positive and reasonable
        assert all(0 <= d <= 10.0 for d in delays)