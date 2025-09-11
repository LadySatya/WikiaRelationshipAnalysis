"""
Exponential backoff and retry logic for failed requests.
"""

from typing import Dict, Optional
import time
import random


class BackoffHandler:
    """Handles exponential backoff for failed requests and error recovery."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 300.0, max_retries: int = 3):
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
        pass
    
    def should_retry(self, url: str, status_code: int, attempt: int) -> bool:
        """Determine if request should be retried based on status and attempts."""
        # Check if we've exceeded max retries
        if attempt > self.max_retries:
            return False
        
        # Check if status code is retriable
        return self._is_retriable_status(status_code)
    
    def record_success(self, url: str) -> None:
        """Record successful request, reset failure count for domain."""
        pass
    
    def record_failure(self, url: str, status_code: int) -> None:
        """Record failed request for backoff calculation."""
        pass
    
    def get_failure_count(self, url: str) -> int:
        """Get current failure count for URL's domain."""
        pass
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        pass
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        pass
    
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
        pass