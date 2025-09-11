"""
HTTP session management with proper headers and connection pooling.
"""

from typing import Optional, Dict, Any
import aiohttp


class SessionManager:
    """Manages HTTP sessions with proper headers and connection pooling."""
    
    def __init__(self, user_agent: str, timeout_seconds: int = 30, max_retries: int = 3):
        """Initialize session manager with user agent and timeout."""
        if not user_agent:
            raise ValueError("user_agent cannot be None" if user_agent is None else "user_agent cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
            
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._session = None
    
    async def create_session(self) -> aiohttp.ClientSession:
        """Create and configure aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
        
        # Configure timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        
        # Configure connector with reasonable limits
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        # Create session with default headers
        self._session = aiohttp.ClientSession(
            headers=self._get_default_headers(),
            timeout=timeout,
            connector=connector
        )
        
        return self._session
    
    async def close_session(self) -> None:
        """Close the current session and cleanup connections."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make GET request with rate limiting and error handling."""
        if not self._session or self._session.closed:
            await self.create_session()
        
        return await self._session.get(url, **kwargs)
    
    async def head(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make HEAD request to check content type/size."""
        if not self._session or self._session.closed:
            await self.create_session()
        
        return await self._session.head(url, **kwargs)
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        return {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',  # Do Not Track
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def _should_retry_response(self, response: aiohttp.ClientResponse) -> bool:
        """Check if response indicates we should retry."""
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
        
        return response.status in retriable_codes
    
    async def _handle_rate_limit_response(self, response: aiohttp.ClientResponse) -> None:
        """Handle rate limit responses (429, 503) with appropriate delays."""
        import asyncio
        
        # Check for Retry-After header
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                # Retry-After can be in seconds or HTTP date
                delay = float(retry_after)
                # Cap the delay to a reasonable maximum
                delay = min(delay, 300)  # Max 5 minutes
                await asyncio.sleep(delay)
                return
            except ValueError:
                # If it's not a number, it might be an HTTP date
                # For now, use a default delay
                pass
        
        # Default delays for rate limiting
        if response.status == 429:
            await asyncio.sleep(60)  # 1 minute for rate limiting
        elif response.status in (503, 502, 504):
            await asyncio.sleep(30)  # 30 seconds for server errors
        else:
            await asyncio.sleep(10)  # 10 seconds for other retriable errors
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close_session()