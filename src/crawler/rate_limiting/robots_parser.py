"""
Robots.txt parsing and compliance checking.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp


class RobotsParser:
    """Handles robots.txt parsing, caching, and compliance checking."""

    def __init__(
            self, user_agent: str, cache_dir: Path, cache_ttl_hours: int = 24
    ):
        """Initialize robots parser with user agent and cache
        settings."""
        if user_agent is None:
            raise ValueError("User agent cannot be None")
        if not user_agent or not user_agent.strip():
            raise ValueError("User agent cannot be empty")

        self.user_agent = user_agent
        self.cache_dir = cache_dir
        self.cache_ttl_hours = cache_ttl_hours

        # In-memory cache of parsed robots.txt files
        # Maps domain -> (RobotFileParser, timestamp)
        self._robots_cache: Dict[str, tuple] = {}

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        if not url or not isinstance(url, str):
            logging.warning("Invalid URL provided to can_fetch")
            return False

        try:
            # Extract domain from URL
            parsed = urlparse(url)
            domain = parsed.netloc

            if not domain:
                logging.warning(f"Cannot extract domain from URL: {url}")
                return False

            # Load robots.txt for this domain
            robots_parser = await self._load_robots_txt(domain)

            # If no robots.txt or failed to load, allow by default
            if robots_parser is None:
                return True

            # Check if the URL can be fetched
            return robots_parser.can_fetch(self.user_agent, url)

        except Exception as e:
            logging.error(f"Error checking robots.txt for {url}: {e}")
            # On error, allow fetching (fail open, not fail closed)
            return True

    async def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get crawl delay for domain from robots.txt."""
        if not url or not isinstance(url, str):
            return None

        try:
            # Extract domain from URL
            parsed = urlparse(url)
            domain = parsed.netloc

            if not domain:
                return None

            # Load robots.txt for this domain
            robots_parser = await self._load_robots_txt(domain)

            # If no robots.txt, no delay specified
            if robots_parser is None:
                return None

            # Get crawl delay for our user agent
            delay = robots_parser.crawl_delay(self.user_agent)

            # Return as float if specified
            if delay is not None:
                return float(delay)

            return None

        except Exception as e:
            logging.error(f"Error getting crawl delay for {url}: {e}")
            return None

    async def _load_robots_txt(self, domain: str) -> Optional[RobotFileParser]:
        """Load robots.txt for domain, using cache if available."""
        if not domain:
            return None

        # Check in-memory cache first
        if domain in self._robots_cache:
            robots_parser, timestamp = self._robots_cache[domain]

            # Check if cache is still valid
            age_hours = (time.time() - timestamp) / 3600
            if age_hours < self.cache_ttl_hours:
                return robots_parser
            else:
                # Cache expired, remove it
                del self._robots_cache[domain]

        # Try to load from file cache
        cache_path = self._get_cache_path(domain)
        if self._is_cache_valid(cache_path):
            content = self._load_from_cache(domain)
            if content is not None:
                # Parse and cache in memory
                robots_parser = RobotFileParser()
                robots_parser.parse(content.splitlines())
                self._robots_cache[domain] = (robots_parser, time.time())
                return robots_parser

        # Cache miss or expired - fetch from server
        content = await self._fetch_robots_txt(domain)

        if content is None:
            # No robots.txt found (404) - cache this result with empty parser
            robots_parser = RobotFileParser()
            robots_parser.parse([])  # Empty rules = allow all
            self._robots_cache[domain] = (robots_parser, time.time())
            return robots_parser

        # Save to cache
        self._save_to_cache(domain, content)

        # Parse and cache in memory
        robots_parser = RobotFileParser()
        robots_parser.parse(content.splitlines())
        self._robots_cache[domain] = (robots_parser, time.time())

        return robots_parser

    def _get_cache_path(self, domain: str) -> Path:
        """Get file path for cached robots.txt."""
        # Use MD5 hash of domain for safe filename
        domain_hash = hashlib.md5(domain.encode("utf-8")).hexdigest()
        return self.cache_dir / f"robots_{domain_hash}.txt"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cached robots.txt is still valid."""
        if not cache_path.exists():
            return False

        try:
            # Check file modification time
            file_mtime = cache_path.stat().st_mtime
            age_hours = (time.time() - file_mtime) / 3600

            return age_hours < self.cache_ttl_hours
        except Exception as e:
            logging.error(f"Error checking cache validity: {e}")
            return False

    async def _fetch_robots_txt(self, domain: str) -> Optional[str]:
        """Fetch robots.txt content from domain."""
        robots_url = f"https://{domain}/robots.txt"

        try:
            # Create a temporary session for fetching robots.txt
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(robots_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        logging.info(f"Fetched robots.txt from {domain}")
                        return content
                    elif response.status == 404:
                        # No robots.txt exists - this is normal
                        logging.info(f"No robots.txt found for {domain} (404)")
                        return None
                    else:
                        logging.warning(
                            f"Unexpected status {response.status} for "
                            f"robots.txt at {domain}"
                        )
                        return None

        except aiohttp.ClientError as e:
            logging.warning(
                f"Network error fetching robots.txt from {domain}: {e}"
            )
            return None
        except Exception as e:
            logging.error(f"Error fetching robots.txt from {domain}: {e}")
            return None

    def _save_to_cache(self, domain: str, content: str) -> None:
        """Save robots.txt content to cache."""
        if not content:
            return

        try:
            cache_path = self._get_cache_path(domain)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)
            logging.debug(f"Saved robots.txt for {domain} to cache")
        except Exception as e:
            logging.error(
                f"Error saving robots.txt to cache for {domain}: {e}"
            )

    def _load_from_cache(self, domain: str) -> Optional[str]:
        """Load robots.txt content from cache."""
        try:
            cache_path = self._get_cache_path(domain)
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logging.debug(f"Loaded robots.txt for {domain} from cache")
                return content
        except Exception as e:
            logging.error(
                f"Error loading robots.txt from cache for {domain}: {e}"
            )

        return None

    def clear_cache(self) -> None:
        """Clear all cached robots.txt files."""
        try:
            # Clear in-memory cache
            self._robots_cache.clear()

            # Clear file cache
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("robots_*.txt"):
                    try:
                        cache_file.unlink()
                        logging.debug(f"Deleted cache file: {cache_file}")
                    except Exception as e:
                        logging.error(
                            f"Error deleting cache file {cache_file}: {e}"
                        )

            logging.info("Cleared all robots.txt cache")
        except Exception as e:
            logging.error(f"Error clearing robots.txt cache: {e}")
