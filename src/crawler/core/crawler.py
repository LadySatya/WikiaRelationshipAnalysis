"""
Main WikiaCrawler class for coordinating the crawling process.
"""

from typing import List, Optional, Dict, Set
from pathlib import Path
import asyncio
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
import logging

from ..rate_limiting import RateLimiter, RobotsParser
from ..core.session_manager import SessionManager
from ..core.url_manager import URLManager
from ..persistence import ContentSaver, CrawlState
from ..extraction.page_extractor import PageExtractor
from ..utils.url_utils import URLUtils


class WikiaCrawler:
    """Main crawler orchestrating the entire crawling process."""
    
    def __init__(self, project_name: str, config: Dict):
        """Initialize crawler with project name and configuration."""
        # Validate project name
        if project_name is None:
            raise ValueError("Project name cannot be None")
        if not project_name or not project_name.strip():
            raise ValueError("Project name cannot be empty")
        
        # Check for invalid characters in project name
        invalid_chars = r'[/\\:*?"<>|]'
        if re.search(invalid_chars, project_name):
            raise ValueError("Project name contains invalid characters")
        
        # Validate configuration
        if config is None:
            raise ValueError("Configuration cannot be None")
        if not config:
            raise ValueError("Configuration cannot be empty")
        
        # Check required configuration keys
        required_keys = [
            'respect_robots_txt',
            'user_agent',
            'default_delay_seconds',
            'target_namespaces'
        ]

        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")

        # Validate configuration types
        if not isinstance(config['respect_robots_txt'], bool):
            raise ValueError("respect_robots_txt must be a boolean")
        if not isinstance(config['default_delay_seconds'], (int, float)):
            raise ValueError("default_delay_seconds must be a number")
        if not isinstance(config['target_namespaces'], list):
            raise ValueError("target_namespaces must be a list")
        
        # Store core attributes
        self.project_name = project_name
        self.config = config.copy()
        
        # Set defaults for optional configuration
        self.timeout_seconds = config.get('timeout_seconds', 30)
        self.max_retries = config.get('max_retries', 3)
        self.exclude_patterns = config.get('exclude_patterns', [])
        
        # Set up project directory structure
        data_dir = Path(config.get('data_dir', './data'))
        self.project_path = data_dir / "projects" / project_name
        self._create_project_structure()
        
        # Initialize components
        self.rate_limiter = RateLimiter(
            default_delay=config['default_delay_seconds']
        )

        # Initialize robots.txt parser if respect_robots_txt is enabled
        self.respect_robots_txt = config['respect_robots_txt']
        if self.respect_robots_txt:
            cache_dir = self.project_path / "cache" / "robots"
            self.robots_parser = RobotsParser(
                user_agent=config['user_agent'],
                cache_dir=cache_dir,
                cache_ttl_hours=24
            )
        else:
            self.robots_parser = None

        self.session_manager = SessionManager(
            user_agent=config['user_agent'],
            timeout_seconds=self.timeout_seconds
        )

        self.url_manager = URLManager(self.project_path)
        self.content_saver = ContentSaver(self.project_path)
        self.crawl_state = CrawlState(self.project_path)
        self.page_extractor = PageExtractor()
    
    def _create_project_structure(self) -> None:
        """Create the project directory structure."""
        directories = [
            "raw",
            "processed",
            "relationships",
            "cache",
            "crawl_state",
            "exports"
        ]

        for directory in directories:
            dir_path = self.project_path / directory
            dir_path.mkdir(parents=True, exist_ok=True)
    
    async def crawl_wikia(self, start_urls: List[str], max_pages: Optional[int] = None) -> Dict:
        """Start crawling from seed URLs, returns crawl statistics."""
        # Input validation
        if start_urls is None:
            raise ValueError("start_urls cannot be None")
        if not start_urls:
            raise ValueError("start_urls cannot be empty")
        
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be positive")
        
        # Validate URLs
        for url in start_urls:
            if not self._is_valid_url(url):
                raise ValueError(f"Invalid URL: {url}")
        
        # Initialize crawl statistics
        stats = {
            'start_time': datetime.now(timezone.utc).isoformat(),
            'pages_crawled': 0,
            'pages_attempted': 0,
            'errors': 0,
            'characters_found': 0,
            'urls_in_queue': 0,
        }
        
        start_time = time.time()
        
        try:
            # Set target domain for domain validation
            self._set_target_domain(start_urls)
            
            # Add start URLs to the queue
            self.url_manager.add_urls(start_urls)
            
            # Main crawling loop
            while True:
                # Check if we've reached the page limit
                if max_pages is not None and stats['pages_crawled'] >= max_pages:
                    break
                
                # Get next URL from queue
                url = self.url_manager.get_next_url()
                if url is None:
                    break  # No more URLs to crawl
                
                stats['pages_attempted'] += 1
                
                try:
                    # Rate limiting
                    await self.rate_limiter.wait_if_needed(url)
                    
                    # Crawl the page
                    page_data = await self._crawl_page(url)
                    
                    if page_data:
                        stats['pages_crawled'] += 1
                        
                        # Count characters found
                        if 'characters_mentioned' in page_data:
                            stats['characters_found'] += len(page_data['characters_mentioned'])
                        
                        # Mark URL as visited
                        self.url_manager.mark_visited(url)
                        
                        # Discover and add new links
                        if 'links' in page_data:
                            new_links = [link for link in page_data['links'] 
                                        if self._should_crawl_url(link)]
                            self.url_manager.add_urls(new_links)
                    else:
                        # Mark as failed if no data returned
                        self.url_manager.mark_failed(url, "No data extracted")
                        stats['errors'] += 1
                        
                except Exception as e:
                    # Log error and continue with next URL
                    logging.error(f"Error crawling {url}: {e}")
                    self.url_manager.mark_failed(url, str(e))
                    stats['errors'] += 1
                
                # Save state periodically
                save_every = self.config.get('save_state_every_n_pages', 10)
                if stats['pages_crawled'] % save_every == 0 and stats['pages_crawled'] > 0:
                    await self._save_crawl_state(stats)
            
            # Final statistics
            end_time = time.time()
            stats.update({
                'end_time': datetime.now(timezone.utc).isoformat(),
                'duration_seconds': end_time - start_time,
                'urls_in_queue': self.url_manager.queue_size(),
            })
            
            # Save final state
            await self._save_crawl_state(stats)
            
            return stats
            
        except Exception as e:
            # Handle any unexpected errors
            end_time = time.time()
            stats.update({
                'end_time': datetime.now(timezone.utc).isoformat(),
                'duration_seconds': end_time - start_time,
                'error': str(e),
            })
            raise
    
    async def resume_crawl(self) -> Dict:
        """Resume an interrupted crawl from saved state."""
        pass
    
    def pause_crawl(self) -> None:
        """Pause the current crawl and save state."""
        pass
    
    def stop_crawl(self) -> None:
        """Stop crawling completely and cleanup resources."""
        pass
    
    async def __aenter__(self):
        """Context manager entry - ensures proper session setup."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session cleanup."""
        await self.cleanup()
    
    async def cleanup(self):
        """Clean up all resources including sessions."""
        try:
            if hasattr(self, 'session_manager'):
                await self.session_manager.close_session()
                logging.info("Session cleanup completed")
        except Exception as e:
            logging.warning(f"Error during session cleanup: {e}")
    
    async def _crawl_page(self, url: str) -> Optional[Dict]:
        """Crawl a single page and return extracted data."""
        try:
            # Check robots.txt compliance if enabled
            if self.respect_robots_txt and self.robots_parser:
                can_fetch = await self.robots_parser.can_fetch(url)
                if not can_fetch:
                    logging.info(f"Robots.txt disallows fetching: {url}")
                    return None

                # Apply crawl delay from robots.txt if specified
                crawl_delay = await self.robots_parser.get_crawl_delay(url)
                if crawl_delay is not None and crawl_delay > 0:
                    domain = urlparse(url).netloc
                    logging.info(f"[ROBOTS.TXT] Applying crawl-delay of {crawl_delay:.2f}s for {domain}")
                    await asyncio.sleep(crawl_delay)
                    logging.debug(f"[ROBOTS.TXT] Crawl-delay wait complete for {domain}")

            # Fetch HTML content using session manager
            response = await self.session_manager.get(url)
            
            try:  # Ensure response is always cleaned up
                if response.status != 200:
                    logging.warning(f"HTTP {response.status} for {url}")
                    return None
                
                html = await response.text()
                
                if not html:
                    return None
                
                # Extract structured content
                extracted_data = self.page_extractor.extract_content(html, url)
                
                # Validate content quality
                if not extracted_data or not extracted_data.get('main_content'):
                    logging.info(f"No main content found for {url}")
                    return None
                
                # Save content to file system
                try:
                    file_path = self.content_saver.save_page_content(url, extracted_data)
                    extracted_data['saved_to'] = str(file_path)
                    logging.info(f"Saved page content to: {file_path}")
                except Exception as save_error:
                    logging.error(f"Failed to save content for {url}: {save_error}")
                
                return extracted_data
                
            finally:
                response.close()  # Ensure response cleanup in all cases
                
        except Exception as e:
            logging.error(f"Error crawling {url}: {e}")
            return None
    
    async def _should_crawl_url_async(self, url: str) -> bool:
        """Check if URL should be crawled based on filters and robots.txt (async version)."""
        if not self._is_valid_url(url):
            return False

        # Ensure we stay on the same wikia domain
        if not self._is_same_wikia_domain(url):
            return False

        # Check against exclude patterns
        exclude_patterns = self.config.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            if pattern in url:
                return False

        # Check robots.txt if enabled (async check)
        if self.respect_robots_txt and self.robots_parser:
            can_fetch = await self.robots_parser.can_fetch(url)
            if not can_fetch:
                return False

        return True

    def _should_crawl_url(self, url: str) -> bool:
        """Check if URL should be crawled based on filters (synchronous checks only)."""
        if not self._is_valid_url(url):
            return False

        # Ensure we stay on the same wikia domain
        if not self._is_same_wikia_domain(url):
            return False

        # Check against exclude patterns
        exclude_patterns = self.config.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            if pattern in url:
                return False

        # Note: robots.txt check happens in _crawl_page for async compatibility
        return True
    
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate that URL is well-formed and uses http/https."""
        if not url or not isinstance(url, str):
            return False
        
        stripped_url = url.strip()
        if not stripped_url:
            return False
        
        try:
            parsed = urlparse(stripped_url)
            return (
                parsed.scheme in ('http', 'https') and
                bool(parsed.netloc)
            )
        except Exception:
            return False
    
    def _is_same_wikia_domain(self, url: str) -> bool:
        """Check if URL belongs to the same wikia domain we're crawling."""
        if not hasattr(self, '_target_domain_url'):
            # No target domain set yet
            return True

        # Use centralized domain validation from URLUtils
        return URLUtils.is_same_wikia_domain(url, self._target_domain_url)
    
    def _set_target_domain(self, start_urls: List[str]) -> None:
        """Set the target domain based on start URLs."""
        if start_urls:
            try:
                self._target_domain_url = start_urls[0]
            except Exception:
                self._target_domain_url = None
    
    async def _save_crawl_state(self, stats: Dict) -> None:
        """Save current crawl state."""
        try:
            state_data = {
                'statistics': stats,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'target_domain_url': getattr(self, '_target_domain_url', None)
            }
            self.crawl_state.save_state(state_data)
        except Exception as e:
            logging.error(f"Failed to save crawl state: {e}")