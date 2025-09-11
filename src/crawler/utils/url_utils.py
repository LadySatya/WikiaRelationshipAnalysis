"""
URL manipulation and validation utilities.
"""

from typing import Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse
import re


class URLUtils:
    """Utilities for URL normalization, validation, and manipulation."""
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL by removing fragments, sorting params, etc."""
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        
        try:
            parsed = urlparse(url.strip())
            
            # Normalize scheme and netloc to lowercase
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            
            # Keep path as-is (preserve case)
            path = parsed.path
            
            # Sort query parameters alphabetically
            if parsed.query:
                from urllib.parse import parse_qsl, urlencode
                sorted_params = sorted(parse_qsl(parsed.query))
                query = urlencode(sorted_params)
            else:
                query = ""
            
            # Remove fragment
            normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
            
            return normalized
            
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid and well-formed."""
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            # Only accept http/https schemes
            if parsed.scheme not in ('http', 'https'):
                return False
            # Netloc cannot be empty or just dots or start with dot
            if not parsed.netloc or parsed.netloc in ('.', '..') or parsed.netloc.startswith('.'):
                return False
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_domain(url: str) -> Optional[str]:
        """Extract domain from URL."""
        if not URLUtils.is_valid_url(url):
            return None
        
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    @staticmethod
    def is_same_domain(url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain."""
        domain1 = URLUtils.get_domain(url1)
        domain2 = URLUtils.get_domain(url2)
        
        if domain1 is None or domain2 is None:
            return False
        
        return domain1 == domain2
    
    @staticmethod
    def resolve_relative_url(base_url: str, relative_url: str) -> str:
        """Resolve relative URL against base URL."""
        if not URLUtils.is_valid_url(base_url):
            raise ValueError("Base URL must be valid")
        
        if not relative_url or not isinstance(relative_url, str):
            raise ValueError("Relative URL must be a non-empty string")
        
        return urljoin(base_url, relative_url.strip())
    
    @staticmethod
    def clean_url_for_filename(url: str) -> str:
        """Convert URL to safe filename."""
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        
        try:
            parsed = urlparse(url.strip())
            
            # Build filename parts
            parts = []
            
            # Add domain
            if parsed.netloc:
                parts.append(parsed.netloc)
            
            # Add path segments
            if parsed.path and parsed.path != '/':
                path_parts = [p for p in parsed.path.strip('/').split('/') if p]
                parts.extend(path_parts)
            
            # Add query parameters
            if parsed.query:
                from urllib.parse import parse_qsl
                query_parts = parse_qsl(parsed.query)
                for key, value in query_parts:
                    parts.extend([key, value])
            
            # Join with underscores and clean
            filename = '_'.join(parts)
            
            # Replace invalid filesystem characters
            invalid_chars = '<>:"|?*\\/'
            for char in invalid_chars:
                filename = filename.replace(char, '_')
            
            # Replace spaces and other problematic chars
            filename = re.sub(r'[\s\t\n\r]+', '_', filename)
            
            # Remove multiple underscores
            filename = re.sub(r'_+', '_', filename)
            
            # Trim underscores from ends
            filename = filename.strip('_')
            
            return filename or 'unnamed'
            
        except Exception:
            return 'invalid_url'
    
    @staticmethod
    def extract_page_title_from_url(url: str) -> Optional[str]:
        """Extract likely page title from URL path."""
        pass
    
    @staticmethod
    def is_wikia_url(url: str) -> bool:
        """Check if URL is from a Wikia/Fandom domain."""
        if not URLUtils.is_valid_url(url):
            return False
        
        domain = URLUtils.get_domain(url)
        if not domain:
            return False
        
        wikia_patterns = [
            '.fandom.com',
            '.wikia.org', 
            '.wikia.com'
        ]
        
        return any(pattern in domain.lower() for pattern in wikia_patterns)
    
    @staticmethod
    def get_wikia_subdomain(url: str) -> Optional[str]:
        """Extract wikia subdomain (e.g., 'harrypotter' from harrypotter.fandom.com)."""
        if not URLUtils.is_wikia_url(url):
            return None
        
        domain = URLUtils.get_domain(url)
        if not domain:
            return None
        
        domain = domain.lower()
        
        # Handle fandom.com domains
        if '.fandom.com' in domain:
            return domain.split('.fandom.com')[0]
        
        # Handle wikia.org/wikia.com domains
        for pattern in ['.wikia.org', '.wikia.com']:
            if pattern in domain:
                return domain.split(pattern)[0]
        
        return None
    
    @staticmethod
    def remove_url_parameters(url: str, keep_params: Optional[Set[str]] = None) -> str:
        """Remove URL parameters except those in keep_params."""
        pass