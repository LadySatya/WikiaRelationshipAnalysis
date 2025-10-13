"""
Rate limiting system to respect website crawling policies.
"""

import asyncio
import logging
import time
from typing import Dict
from urllib.parse import urlparse


class RateLimiter:
    """Per-domain rate limiting with configurable delays."""

    def __init__(self, default_delay: float = 1.0):
        """Initialize rate limiter with default settings."""
        if default_delay <= 0:
            raise ValueError("delay must be positive")

        self.default_delay = default_delay

        # Domain-specific tracking
        self._domain_delays = {}
        self._domain_requests = {}  # domain -> list of timestamps

    async def wait_if_needed(self, url: str) -> None:
        """Wait if needed before making request to URL's domain."""
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")

        domain = self._get_domain(url)
        if not domain:
            raise ValueError("Invalid URL: cannot extract domain")

        # Check if this is first request to domain
        requests = self._domain_requests.get(domain, [])

        if requests:
            # Not the first request - always wait the configured delay
            delay = self._domain_delays.get(domain, self.default_delay)
            logging.info(
                f"[RATE LIMIT] Waiting {delay:.2f}s before request to "
                f"{domain}"
            )
            await asyncio.sleep(delay)
            logging.debug(f"[RATE LIMIT] Wait complete for {domain}")
        else:
            # First request to domain - no delay needed
            logging.debug(
                f"[RATE LIMIT] First request to {domain}, no delay needed"
            )

        # Record this request
        self.record_request(url)

    def set_domain_delay(self, domain: str, delay_seconds: float) -> None:
        """Set custom delay for specific domain."""
        if delay_seconds <= 0:
            raise ValueError("delay must be positive")
        self._domain_delays[domain] = delay_seconds

    def record_request(self, url: str) -> None:
        """Record that a request was made to this domain."""
        domain = self._get_domain(url)
        current_time = time.time()

        if domain not in self._domain_requests:
            self._domain_requests[domain] = []

        self._domain_requests[domain].append(current_time)

    def get_domain_stats(self, domain: str) -> Dict:
        """Get current stats for domain (requests, last request time,
        etc.)."""
        requests = self._domain_requests.get(domain, [])

        return {
            "request_count": len(requests),
            "last_request_time": requests[-1] if requests else None,
            "delay_seconds": self._domain_delays.get(
                domain, self.default_delay
            ),
        }

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if parsed.scheme not in ("http", "https"):
                raise ValueError("Unsupported URL scheme")
            return parsed.netloc.lower()
        except Exception as e:
            raise ValueError(f"Cannot parse URL: {e}")
