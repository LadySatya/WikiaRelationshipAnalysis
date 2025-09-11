"""
Intelligent link discovery for finding related character and lore pages.
"""

from typing import Set, List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class LinkDiscoverer:
    """Discovers and prioritizes relevant links for crawling."""
    
    def __init__(self, base_domain: Optional[str] = None, target_namespaces: Optional[List[str]] = None):
        """Initialize with domain and namespace filters."""
        self.base_domain = base_domain or "fandom.com"
        self.target_namespaces = target_namespaces or ["Main", "Category"]
        
        # Non-content namespaces that should be deprioritized or excluded
        self.non_content_namespaces = [
            'template:', 'user:', 'talk:', 'help:', 'special:', 'file:',
            'mediawiki:', 'user_talk:', 'project:', 'project_talk:',
            'file_talk:', 'template_talk:', 'category_talk:', 'forum:'
        ]
    
    def discover_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Set[str]]:
        """Discover and categorize links by priority using simplified three-category system."""
        if not soup or not base_url:
            return {'high_priority': set(), 'medium_priority': set(), 'low_priority': set()}
        
        # Find all three types of links
        category_links = self.find_category_links(soup, base_url)
        content_links = self.find_content_links(soup, base_url)
        non_content_links = self.find_non_content_links(soup, base_url)
        
        # Prioritize all links with simplified scoring
        all_links = category_links | content_links | non_content_links
        prioritized = self.prioritize_links_simplified(all_links, base_url)
        
        # Categorize by priority score
        result = {'high_priority': set(), 'medium_priority': set(), 'low_priority': set()}
        
        # Split prioritized list into categories
        for link in prioritized[:30]:  # Top 30 are high priority (categories first)
            result['high_priority'].add(link if isinstance(link, str) else link[0])
        for link in prioritized[30:100]:  # Next 70 are medium priority (content)
            result['medium_priority'].add(link if isinstance(link, str) else link[0])
        for link in prioritized[100:]:  # Rest are low priority (non-content, if any)
            result['low_priority'].add(link if isinstance(link, str) else link[0])
        
        return result
    
    def find_content_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Find content links (main namespace pages that aren't categories)."""
        if not soup:
            return set()
        
        content_links = set()
        
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            
            # Normalize URL
            normalized_url = self._normalize_url(href, base_url)
            if not normalized_url:
                continue
            
            # Apply domain filtering - only same wikia
            if not self._is_same_wikia_domain(normalized_url, base_url):
                continue
            
            # Check if it's a content link
            if self.is_content_link(normalized_url):
                content_links.add(normalized_url)
        
        return content_links
    
    def find_non_content_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Find non-content links (templates, user pages, etc.)."""
        if not soup:
            return set()
        
        non_content_links = set()
        
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            
            # Normalize URL
            normalized_url = self._normalize_url(href, base_url)
            if not normalized_url:
                continue
            
            # Apply domain filtering - only same wikia
            if not self._is_same_wikia_domain(normalized_url, base_url):
                continue
            
            # Check if it's a non-content link
            if self.is_non_content_link(normalized_url):
                non_content_links.add(normalized_url)
        
        return non_content_links
    
    def find_category_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Find category page links for systematic crawling."""
        if not soup:
            return set()
        
        category_links = set()
        
        # Look for category links in common locations
        category_selectors = [
            '.categories a', '#catlinks a', '.page-categories a',
            'a[href*="Category:"]', 'a[href*="/wiki/Category"]'
        ]
        
        for selector in category_selectors:
            for link_tag in soup.select(selector):
                href = link_tag.get('href')
                if href:
                    normalized_url = self._normalize_url(href, base_url)
                    if normalized_url and self._is_same_wikia_domain(normalized_url, base_url):
                        category_links.add(normalized_url)
        
        return category_links
    
    
    def prioritize_links(self, links: Set[str], current_url: str) -> List[str]:
        """Sort links by crawling priority (legacy method)."""
        return self.prioritize_links_simplified(links, current_url)
    
    def prioritize_links_simplified(self, links: Set[str], current_url: str) -> List[str]:
        """Sort links by simplified three-category priority system."""
        if not links:
            return []
        
        scored_links = []
        
        for link in links:
            score = 0
            link_lower = link.lower()
            
            # SIMPLIFIED THREE-CATEGORY SYSTEM
            
            # Category pages get highest priority (300 points)
            if '/category' in link_lower and 'category:' in link_lower:
                score += 300
            
            # Content pages get medium priority (100 points)
            elif self.is_content_link(link):
                score += 100
            
            # Non-content pages get low/negative priority (-50 points)
            elif self.is_non_content_link(link):
                score -= 50
            
            # Default for other links
            else:
                score += 50
            
            scored_links.append((link, score))
        
        # Sort by score (descending) and return just the URLs
        sorted_links = sorted(scored_links, key=lambda x: x[1], reverse=True)
        return [link for link, score in sorted_links]
    
    def is_internal_link(self, url: str) -> bool:
        """Check if link is internal to the target wikia."""
        if not url:
            return False
        
        # Check if it's a relative URL (internal by default)
        if url.startswith('/'):
            return True
        
        # Check if it contains our base domain
        if self.base_domain in url.lower():
            return True
        
        # Check for wikia/fandom domains
        wikia_domains = ['fandom.com', 'wikia.org', 'wikia.com']
        return any(domain in url.lower() for domain in wikia_domains)
    
    def is_content_link(self, url: str) -> bool:
        """Check if link is a content page (main namespace, not category)."""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Must be in main namespace (starts with /wiki/ but not special pages)
        if not '/wiki/' in url_lower:
            return False
        
        # Not a category page
        if '/wiki/category:' in url_lower:
            return False
        
        # Not a non-content namespace
        if any(namespace in url_lower for namespace in self.non_content_namespaces):
            return False
        
        return True
    
    def is_non_content_link(self, url: str) -> bool:
        """Check if link is a non-content page (template, user, etc.)."""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Check if it's in a non-content namespace
        return any(namespace in url_lower for namespace in self.non_content_namespaces)
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """Normalize and resolve relative URLs."""
        if not url:
            return ""
        
        url = url.strip()
        
        # Handle relative URLs
        if url.startswith('/'):
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        elif not url.startswith(('http:', 'https:')):
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        
        return url
    
    def _get_link_context(self, link_tag, soup: BeautifulSoup) -> str:
        """Get context around a link for classification."""
        if not link_tag:
            return ""
        
        context_text = ""
        
        # Get text from parent elements for context
        parent = link_tag.parent
        if parent:
            context_text = parent.get_text(strip=True)[:200]  # Limit context size
        
        # Also get surrounding text
        if link_tag.previous_sibling:
            prev_text = str(link_tag.previous_sibling)[-50:] if link_tag.previous_sibling else ""
            context_text = prev_text + " " + context_text
        
        if link_tag.next_sibling:
            next_text = str(link_tag.next_sibling)[:50] if link_tag.next_sibling else ""
            context_text = context_text + " " + next_text
        
        return context_text.strip()
    
    def _extract_link_text(self, link_tag) -> str:
        """Extract and clean text from link tag."""
        if not link_tag:
            return ""
        
        # Get text content
        text = link_tag.get_text(strip=True)
        
        # If no text, try title attribute
        if not text:
            text = link_tag.get('title', '')
        
        # If still no text, try href for filename
        if not text:
            href = link_tag.get('href', '')
            if href:
                # Extract filename from URL
                parts = href.split('/')
                if parts:
                    text = parts[-1].replace('_', ' ')
        
        return text.strip()
    
    def _is_same_wikia_domain(self, href: str, base_url: str) -> bool:
        """Check if href belongs to the same wikia domain as base_url."""
        from urllib.parse import urlparse
        
        # Handle relative URLs - they're always same domain
        if href.startswith('/'):
            return True
        
        # Handle fragment-only URLs (#section)
        if href.startswith('#'):
            return True
        
        # Handle protocol-relative URLs
        if href.startswith('//'):
            href = 'https:' + href
        
        try:
            base_domain = urlparse(base_url).netloc.lower()
            href_domain = urlparse(href).netloc.lower()
            
            # Exclude Fandom platform meta-domains
            fandom_meta_domains = [
                'community.fandom.com',
                'fandom.zendesk.com', 
                'about.fandom.com',
                'auth.fandom.com'
            ]
            
            if href_domain in fandom_meta_domains:
                return False
            
            # Exact domain match
            if base_domain == href_domain:
                return True
            
            # Check if both are wikia/fandom domains
            if self._is_wikia_domain(base_domain) and self._is_wikia_domain(href_domain):
                base_wikia = self._extract_wikia_name(base_domain)
                href_wikia = self._extract_wikia_name(href_domain)
                return base_wikia == href_wikia
            
            return False
        except Exception:
            return False
    
    def _is_wikia_domain(self, domain: str) -> bool:
        """Check if domain is a wikia/fandom domain."""
        wikia_domains = ['fandom.com', 'wikia.org', 'wikia.com']
        return any(wikia_domain in domain for wikia_domain in wikia_domains)
    
    def _extract_wikia_name(self, domain: str) -> str:
        """Extract wikia name from domain."""
        # Handle different domain formats
        if '.fandom.com' in domain:
            return domain.split('.fandom.com')[0]
        elif '.wikia.org' in domain:
            return domain.split('.wikia.org')[0]
        elif '.wikia.com' in domain:
            return domain.split('.wikia.com')[0]
        return domain