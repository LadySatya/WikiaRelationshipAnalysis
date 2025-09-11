"""
Rate limiting system to respect website crawling policies.
"""

from typing import Dict, Optional
import time
import asyncio
from urllib.parse import urlparse


class RateLimiter:
    """Per-domain rate limiting with configurable delays and burst protection."""
    
    def __init__(self, default_delay: float = 1.0, requests_per_minute: int = 60):
        """Initialize rate limiter with default settings."""
        if default_delay <= 0:
            raise ValueError("delay must be positive")
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        
        self.default_delay = default_delay
        self.requests_per_minute = requests_per_minute
        
        # Domain-specific tracking
        self._domain_delays = {}
        self._domain_requests = {}  # domain -> list of timestamps
        self._domain_rate_limits = {}
    
    async def wait_if_needed(self, url: str) -> None:
        """Wait if needed before making request to URL's domain."""
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        
        domain = self._get_domain(url)
        if not domain:
            raise ValueError("Invalid URL: cannot extract domain")
        
        # Calculate wait time needed
        wait_time = self._calculate_wait_time(domain)
        
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        # Record this request
        self.record_request(url)
    
    def set_domain_delay(self, domain: str, delay_seconds: float) -> None:
        """Set custom delay for specific domain."""
        if delay_seconds <= 0:
            raise ValueError("delay must be positive")
        self._domain_delays[domain] = delay_seconds
    
    def set_domain_rate_limit(self, domain: str, requests_per_minute: int) -> None:
        """Set requests per minute limit for specific domain."""
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self._domain_rate_limits[domain] = requests_per_minute
    
    def record_request(self, url: str) -> None:
        """Record that a request was made to this domain."""
        domain = self._get_domain(url)
        current_time = time.time()
        
        if domain not in self._domain_requests:
            self._domain_requests[domain] = []
        
        self._domain_requests[domain].append(current_time)
        
        # Clean up old requests
        self._cleanup_old_requests(domain)
    
    def get_domain_stats(self, domain: str) -> Dict:
        """Get current stats for domain (requests, last request time, etc.)."""
        requests = self._domain_requests.get(domain, [])
        
        return {
            'request_count': len(requests),
            'last_request_time': requests[-1] if requests else None,
            'delay_seconds': self._domain_delays.get(domain, self.default_delay),
            'requests_per_minute': self._domain_rate_limits.get(domain, self.requests_per_minute),
            'current_requests_in_window': len([r for r in requests if time.time() - r <= 60])
        }
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("Unsupported URL scheme")
            return parsed.netloc.lower()
        except Exception as e:
            raise ValueError(f"Cannot parse URL: {e}")
    
    def _is_rate_limited(self, domain: str) -> bool:
        """Check if domain is currently rate limited."""
        pass
    
    def _calculate_wait_time(self, domain: str) -> float:
        """Calculate how long to wait before next request to domain."""
        requests = self._domain_requests.get(domain, [])
        
        if not requests:
            return 0.0  # First request to this domain
        
        last_request_time = requests[-1]
        delay = self._domain_delays.get(domain, self.default_delay)
        
        # Time since last request
        time_since_last = time.time() - last_request_time
        
        # Basic delay-based wait time
        delay_wait = max(0, delay - time_since_last)
        
        # Rate limit check (requests per minute)
        rate_limit = self._domain_rate_limits.get(domain, self.requests_per_minute)
        one_minute_ago = time.time() - 60
        recent_requests = [r for r in requests if r > one_minute_ago]
        
        if len(recent_requests) >= rate_limit:
            # Need to wait until oldest request in window expires
            oldest_request = min(recent_requests)
            rate_limit_wait = (oldest_request + 60) - time.time()
            return max(delay_wait, rate_limit_wait)
        
        return delay_wait
    
    def _cleanup_old_requests(self, domain: str) -> None:
        """Remove request timestamps older than 1 minute."""
        if domain not in self._domain_requests:
            return
        
        one_minute_ago = time.time() - 60
        self._domain_requests[domain] = [
            timestamp for timestamp in self._domain_requests[domain] 
            if timestamp > one_minute_ago
        ]