"""
Exponential backoff and retry logic for failed requests.
"""

import asyncio
import logging
import random
from urllib.parse import urlparse


class BackoffHandler:
    """Handles exponential backoff for failed requests and error recovery."""

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 300.0,
        max_retries: int = 3
    ):
        """Initialize backoff handler with timing parameters."""
        if base_delay <= 0:
            raise ValueError("base_delay must be positive")
        if max_delay <= 0:
            raise ValueError("max_delay must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if max_delay < base_delay:
            raise ValueError("max_delay must be >= base_delay")

        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

        # Track failures per domain
        self._domain_failures = {}

    async def wait_with_backoff(self, url: str, attempt: int) -> None:
        """Wait with exponential backoff based on attempt number."""
        if attempt <= 0:
            return  # No wait for first attempt or invalid attempts

        delay = self._calculate_delay(attempt)
        domain = self._get_domain(url)
        logging.warning(
            f"[BACKOFF] Retry attempt {attempt} for {domain}: "
            f"waiting {delay:.2f}s before retrying"
        )
        await asyncio.sleep(delay)
        logging.debug(
            f"[BACKOFF] Backoff wait complete for attempt {attempt} ({domain})"
        )

    def should_retry(
            self, url: str, status_code: int, attempt: int
    ) -> bool:
        """Determine if request should be retried based on status and
        attempts."""
        # Check if we've exceeded max retries
        if attempt > self.max_retries:
            return False

        # Check if status code is retriable
        return self._is_retriable_status(status_code)

    def record_success(self, url: str) -> None:
        """Record successful request, reset failure count for domain."""
        domain = self._get_domain(url)
        if domain in self._domain_failures:
            self._domain_failures[domain] = 0

    def record_failure(self, url: str, status_code: int) -> None:
        """Record failed request for backoff calculation."""
        domain = self._get_domain(url)
        if domain not in self._domain_failures:
            self._domain_failures[domain] = 0
        self._domain_failures[domain] += 1

    def get_failure_count(self, url: str) -> int:
        """Get current failure count for URL's domain."""
        domain = self._get_domain(url)
        return self._domain_failures.get(domain, 0)

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower() or url
        except Exception:
            return url

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        # Exponential backoff: base_delay * 2^(attempt-1)
        delay = self.base_delay * (2 ** (attempt - 1))

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter (±25% randomization)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        delay = max(0, delay + jitter)

        # Ensure final delay doesn't exceed max_delay due to positive jitter
        delay = min(delay, self.max_delay)

        return delay

    def _is_retriable_status(self, status_code: int) -> bool:
        """Check if HTTP status code indicates request should be retried."""
        # Server errors and rate limiting that are typically temporary
        retriable_codes = {
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
            520,  # Cloudflare: Unknown Error
            521,  # Cloudflare: Web Server Is Down
            522,  # Cloudflare: Connection Timed Out
            523,  # Cloudflare: Origin Is Unreachable
            524,  # Cloudflare: A Timeout Occurred
        }

        return status_code in retriable_codes

    def reset_domain_failures(self, domain: str) -> None:
        """Reset failure count for domain."""
        if domain in self._domain_failures:
            self._domain_failures[domain] = 0
