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
        pass
    
    async def wait_with_backoff(self, url: str, attempt: int) -> None:
        """Wait with exponential backoff based on attempt number."""
        pass
    
    def should_retry(self, url: str, status_code: int, attempt: int) -> bool:
        """Determine if request should be retried based on status and attempts."""
        pass
    
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
        pass
    
    def reset_domain_failures(self, domain: str) -> None:
        """Reset failure count for domain."""
        pass