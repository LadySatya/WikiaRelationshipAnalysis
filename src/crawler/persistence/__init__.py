"""
Data persistence and state management components.
"""

from .crawl_state import CrawlState
from .content_saver import ContentSaver

__all__ = ['CrawlState', 'ContentSaver']