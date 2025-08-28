"""
Wikia web crawler module for character relationship analysis.
"""

from .core.crawler import WikiaCrawler
from .core.session_manager import SessionManager
from .core.url_manager import URLManager

__all__ = ['WikiaCrawler', 'SessionManager', 'URLManager']