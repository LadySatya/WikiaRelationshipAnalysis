"""
Tests for WikiaCrawler.crawl_wikia method.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import asyncio
from pathlib import Path
import tempfile
import shutil

from src.crawler.core.crawler import WikiaCrawler
# Mark all tests in this module as unit tests (all use mocks, no real I/O)
pytestmark = pytest.mark.unit


class TestCrawlWikia:
    """Test WikiaCrawler.crawl_wikia method with various scenarios."""
    
    @pytest.fixture
    def basic_config(self):
        """Basic valid configuration for testing."""
        return {
            'respect_robots_txt': True,
            'user_agent': 'WikiaAnalyzer/0.1.0',
            'default_delay_seconds': 1.0,
            'max_requests_per_minute': 60,
            'target_namespaces': ['Main', 'Character'],
            'exclude_patterns': ['User:', 'Template:'],
        }
    
    @pytest.fixture
    def mock_components(self):
        """Mock all crawler components."""
        with patch('src.crawler.core.crawler.RateLimiter') as mock_rate_limiter, \
             patch('src.crawler.core.crawler.SessionManager') as mock_session_manager, \
             patch('src.crawler.core.crawler.URLManager') as mock_url_manager, \
             patch('src.crawler.core.crawler.ContentSaver') as mock_content_saver, \
             patch('src.crawler.core.crawler.CrawlState') as mock_crawl_state:
            
            # Make rate limiter methods async
            mock_rate_limiter.return_value.wait_if_needed = AsyncMock()
            
            yield {
                'rate_limiter': mock_rate_limiter.return_value,
                'session_manager': mock_session_manager.return_value, 
                'url_manager': mock_url_manager.return_value,
                'content_saver': mock_content_saver.return_value,
                'crawl_state': mock_crawl_state.return_value
            }
    
    @pytest.fixture
    def crawler_with_mocks(self, basic_config, mock_components):
        """Create crawler instance with mocked components."""
        return WikiaCrawler("test_project", basic_config)
    
    # Input Validation Tests
    @pytest.mark.asyncio
    async def test_crawl_wikia_empty_start_urls(self, crawler_with_mocks):
        """Test crawl_wikia with empty start_urls list."""
        with pytest.raises(ValueError, match="start_urls cannot be empty"):
            await crawler_with_mocks.crawl_wikia([])
    
    @pytest.mark.asyncio
    async def test_crawl_wikia_none_start_urls(self, crawler_with_mocks):
        """Test crawl_wikia with None start_urls."""
        with pytest.raises(ValueError, match="start_urls cannot be None"):
            await crawler_with_mocks.crawl_wikia(None)
    
    @pytest.mark.asyncio
    async def test_crawl_wikia_invalid_urls(self, crawler_with_mocks):
        """Test crawl_wikia with invalid URLs."""
        invalid_urls = [
            "not_a_url",
            "ftp://invalid.protocol.com",
            "https://",
            ""
        ]
        
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid URL"):
                await crawler_with_mocks.crawl_wikia([invalid_url])
    
    @pytest.mark.asyncio 
    async def test_crawl_wikia_negative_max_pages(self, crawler_with_mocks):
        """Test crawl_wikia with negative max_pages."""
        with pytest.raises(ValueError, match="max_pages must be positive"):
            await crawler_with_mocks.crawl_wikia(
                ["https://naruto.fandom.com"], max_pages=-1
            )
    
    @pytest.mark.asyncio
    async def test_crawl_wikia_zero_max_pages(self, crawler_with_mocks):
        """Test crawl_wikia with zero max_pages."""
        with pytest.raises(ValueError, match="max_pages must be positive"):
            await crawler_with_mocks.crawl_wikia(
                ["https://naruto.fandom.com"], max_pages=0
            )
    
    # Basic Functionality Tests
    @pytest.mark.asyncio
    async def test_crawl_wikia_single_url_success(self, crawler_with_mocks, mock_components):
        """Test successful crawl of single URL."""
        # Setup mocks
        mock_components['url_manager'].get_next_url.side_effect = [
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki", 
            None  # End of queue
        ]
        mock_components['url_manager'].visited_count.return_value = 1
        mock_components['url_manager'].queue_size.return_value = 0
        
        # Mock successful page crawl
        crawler_with_mocks._crawl_page = AsyncMock(return_value={
            'url': 'https://naruto.fandom.com/wiki/Naruto_Uzumaki',
            'title': 'Naruto Uzumaki',
            'content': 'Some content...',
            'links': ['https://naruto.fandom.com/wiki/Sasuke_Uchiha']
        })
        
        result = await crawler_with_mocks.crawl_wikia([
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki"
        ], max_pages=1)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert 'pages_crawled' in result
        assert 'start_time' in result
        assert 'end_time' in result
        assert 'duration_seconds' in result
        assert result['pages_crawled'] == 1
    
    @pytest.mark.asyncio
    async def test_crawl_wikia_multiple_start_urls(self, crawler_with_mocks, mock_components):
        """Test crawl with multiple starting URLs."""
        start_urls = [
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki",
            "https://naruto.fandom.com/wiki/Sasuke_Uchiha"
        ]
        
        # Mock URL manager to return both URLs
        mock_components['url_manager'].get_next_url.side_effect = start_urls + [None]
        mock_components['url_manager'].visited_count.return_value = 2
        
        crawler_with_mocks._crawl_page = AsyncMock(return_value={
            'url': 'test_url', 'title': 'Test', 'content': 'content'
        })
        
        result = await crawler_with_mocks.crawl_wikia(start_urls, max_pages=2)
        
        # Verify both URLs were added to manager
        assert mock_components['url_manager'].add_urls.called
        call_args = mock_components['url_manager'].add_urls.call_args[0][0]
        assert set(call_args) == set(start_urls)
    
    @pytest.mark.asyncio
    async def test_crawl_wikia_max_pages_enforcement(self, crawler_with_mocks, mock_components):
        """Test that max_pages limit is enforced."""
        # Mock URL manager to have many URLs available
        mock_components['url_manager'].get_next_url.side_effect = [
            f"https://naruto.fandom.com/page{i}" for i in range(10)
        ] + [None]
        mock_components['url_manager'].visited_count.return_value = 3
        
        crawler_with_mocks._crawl_page = AsyncMock(return_value={
            'url': 'test_url', 'title': 'Test', 'content': 'content'
        })
        
        result = await crawler_with_mocks.crawl_wikia([
            "https://naruto.fandom.com/start"
        ], max_pages=3)
        
        # Verify only max_pages were crawled
        assert result['pages_crawled'] == 3
        assert crawler_with_mocks._crawl_page.call_count == 3
    
    # Rate Limiting Integration Tests
    @pytest.mark.asyncio
    async def test_crawl_wikia_calls_rate_limiter(self, crawler_with_mocks, mock_components):
        """Test that rate limiter is called for each request."""
        mock_components['url_manager'].get_next_url.side_effect = [
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki", 
            None
        ]
        
        crawler_with_mocks._crawl_page = AsyncMock(return_value={
            'url': 'test_url', 'title': 'Test', 'content': 'content'
        })
        
        await crawler_with_mocks.crawl_wikia([
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki"
        ], max_pages=1)
        
        # Verify rate limiter was called
        mock_components['rate_limiter'].wait_if_needed.assert_called()
    
    # Error Handling Tests
    @pytest.mark.asyncio
    async def test_crawl_wikia_handles_page_crawl_errors(self, crawler_with_mocks, mock_components):
        """Test that page crawl errors don't stop entire crawl."""
        mock_components['url_manager'].get_next_url.side_effect = [
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki",
            "https://naruto.fandom.com/wiki/Sasuke_Uchiha",
            None
        ]
        
        # First page fails, second succeeds
        crawler_with_mocks._crawl_page = AsyncMock(side_effect=[
            Exception("Network error"),
            {'url': 'test_url', 'title': 'Test', 'content': 'content'}
        ])
        
        result = await crawler_with_mocks.crawl_wikia([
            "https://naruto.fandom.com/start"
        ], max_pages=2)
        
        # Should have attempted both pages but only succeeded on one
        assert result['pages_attempted'] == 2
        assert result['pages_crawled'] == 1
        assert result['errors'] == 1
    
    @pytest.mark.asyncio
    async def test_crawl_wikia_handles_url_manager_errors(self, crawler_with_mocks, mock_components):
        """Test handling of URL manager errors."""
        mock_components['url_manager'].add_urls.side_effect = Exception("URL manager error")
        
        with pytest.raises(Exception, match="URL manager error"):
            await crawler_with_mocks.crawl_wikia([
                "https://naruto.fandom.com/wiki/Naruto_Uzumaki"
            ])
    
    # State Management Tests
    @pytest.mark.asyncio
    async def test_crawl_wikia_saves_state_periodically(self, crawler_with_mocks, mock_components):
        """Test that crawl state is saved periodically."""
        # Set save_state_every_n_pages to 2
        crawler_with_mocks.config['save_state_every_n_pages'] = 2
        
        mock_components['url_manager'].get_next_url.side_effect = [
            f"https://naruto.fandom.com/page{i}" for i in range(3)
        ] + [None]
        
        crawler_with_mocks._crawl_page = AsyncMock(return_value={
            'url': 'test_url', 'title': 'Test', 'content': 'content'
        })
        
        await crawler_with_mocks.crawl_wikia([
            "https://naruto.fandom.com/start"
        ], max_pages=3)
        
        # Should save state after page 2 (once during crawl, once at end)
        assert mock_components['crawl_state'].save_state.call_count >= 1
    
    # Return Value Tests  
    @pytest.mark.asyncio
    async def test_crawl_wikia_returns_complete_statistics(self, crawler_with_mocks, mock_components):
        """Test that crawl_wikia returns complete statistics dictionary."""
        mock_components['url_manager'].get_next_url.side_effect = [
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki", 
            None
        ]
        mock_components['url_manager'].visited_count.return_value = 1
        mock_components['url_manager'].queue_size.return_value = 0
        
        crawler_with_mocks._crawl_page = AsyncMock(return_value={
            'url': 'test_url', 'title': 'Test', 'content': 'content',
            'characters_mentioned': ['Naruto', 'Sasuke']
        })
        
        result = await crawler_with_mocks.crawl_wikia([
            "https://naruto.fandom.com/wiki/Naruto_Uzumaki"
        ])
        
        # Check all expected keys are present
        expected_keys = [
            'pages_crawled', 'pages_attempted', 'errors', 'characters_found',
            'start_time', 'end_time', 'duration_seconds', 'urls_in_queue'
        ]
        
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
        
        # Check data types
        assert isinstance(result['pages_crawled'], int)
        assert isinstance(result['duration_seconds'], (int, float))
        assert result['duration_seconds'] >= 0
    
    @pytest.mark.asyncio
    async def test_crawl_wikia_no_max_pages_limit(self, crawler_with_mocks, mock_components):
        """Test crawl without max_pages limit uses all available URLs."""
        available_urls = [f"https://naruto.fandom.com/page{i}" for i in range(5)]
        mock_components['url_manager'].get_next_url.side_effect = available_urls + [None]
        mock_components['url_manager'].visited_count.return_value = 5
        
        crawler_with_mocks._crawl_page = AsyncMock(return_value={
            'url': 'test_url', 'title': 'Test', 'content': 'content'
        })
        
        # Call without max_pages
        result = await crawler_with_mocks.crawl_wikia([
            "https://naruto.fandom.com/start"
        ])
        
        # Should crawl all available URLs
        assert result['pages_crawled'] == 5
        assert crawler_with_mocks._crawl_page.call_count == 5