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
        self.target_namespaces = target_namespaces or ["Main", "Character", "Location"]
        
        # Relationship detection patterns
        self.relationship_keywords = {
            'family': ['father', 'mother', 'son', 'daughter', 'brother', 'sister', 'parent', 'child', 'family', 'relative'],
            'romantic': ['love', 'lover', 'boyfriend', 'girlfriend', 'husband', 'wife', 'married', 'romance', 'relationship'],
            'friendship': ['friend', 'ally', 'companion', 'partner', 'teammate', 'comrade'],
            'rivalry': ['rival', 'enemy', 'opponent', 'nemesis', 'antagonist', 'villain'],
            'mentor': ['teacher', 'mentor', 'master', 'instructor', 'student', 'apprentice', 'disciple', 'pupil'],
            'team': ['team', 'squad', 'group', 'clan', 'organization', 'village', 'guild']
        }
        
        # Character detection patterns (generalized)
        self.character_indicators = [
            'character', 'person', 'individual', 'hero', 'protagonist', 'antagonist',
            'main', 'villain', 'leader', 'member', 'user'
        ]
        
        # Location indicators (generalized)
        self.location_indicators = [
            'place', 'location', 'area', 'region', 'territory', 'zone', 'realm', 'world',
            'city', 'town', 'village', 'country', 'land', 'continent', 'planet',
            'forest', 'mountain', 'desert', 'ocean', 'island', 'building', 'structure'
        ]
    
    def discover_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Set[str]]:
        """Discover and categorize links by priority."""
        if not soup or not base_url:
            return {'high_priority': set(), 'medium_priority': set(), 'low_priority': set()}
        
        # Find different types of links
        character_links = self.find_character_links(soup, base_url)
        location_links = self.find_location_links(soup, base_url)
        category_links = self.find_category_links(soup, base_url)
        
        # Prioritize all links
        all_links = character_links | location_links | category_links
        prioritized = self.prioritize_links(all_links, base_url)
        
        # Categorize by priority score
        result = {'high_priority': set(), 'medium_priority': set(), 'low_priority': set()}
        
        # Split prioritized list into categories (assuming prioritize_links returns scored tuples)
        for link in prioritized[:20]:  # Top 20 are high priority
            result['high_priority'].add(link if isinstance(link, str) else link[0])
        for link in prioritized[20:50]:  # Next 30 are medium priority
            result['medium_priority'].add(link if isinstance(link, str) else link[0])
        for link in prioritized[50:]:  # Rest are low priority
            result['low_priority'].add(link if isinstance(link, str) else link[0])
        
        return result
    
    def find_character_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Find links likely pointing to character pages."""
        if not soup:
            return set()
        
        character_links = set()
        
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            link_text = self._extract_link_text(link_tag)
            
            # Normalize URL
            normalized_url = self._normalize_url(href, base_url)
            if not normalized_url or not self.is_internal_link(normalized_url):
                continue
            
            # Check if it's a character link
            if self.is_character_link(normalized_url, link_text):
                character_links.add(normalized_url)
        
        return character_links
    
    def find_location_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Find links likely pointing to location pages."""
        if not soup:
            return set()
        
        location_links = set()
        
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            link_text = self._extract_link_text(link_tag)
            
            # Normalize URL
            normalized_url = self._normalize_url(href, base_url)
            if not normalized_url or not self.is_internal_link(normalized_url):
                continue
            
            # Check if it's a location link
            if self.is_location_link(normalized_url, link_text):
                location_links.add(normalized_url)
        
        return location_links
    
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
                    if normalized_url and self.is_internal_link(normalized_url):
                        category_links.add(normalized_url)
        
        return category_links
    
    def prioritize_links(self, links: Set[str], current_url: str) -> List[str]:
        """Sort links by crawling priority."""
        if not links:
            return []
        
        scored_links = []
        
        for link in links:
            score = 0
            link_lower = link.lower()
            
            # Character links get high base score
            if '/character' in link_lower or any(indicator in link_lower for indicator in self.character_indicators):
                score += 100
            
            # Location links get medium base score  
            if '/location' in link_lower or any(indicator in link_lower for indicator in self.location_indicators):
                score += 50
            
            # Category links get lower score but still valuable
            if '/category' in link_lower:
                score += 30
            
            # Main namespace gets bonus
            if '/wiki/' in link_lower and '/wiki/Category' not in link_lower and '/wiki/Template' not in link_lower:
                score += 25
            
            # Boost for relationship-related terms in URL
            for relationship_type, keywords in self.relationship_keywords.items():
                if any(keyword in link_lower for keyword in keywords):
                    score += 75  # High boost for relationship content
                    break
            
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
    
    def is_character_link(self, url: str, link_text: str) -> bool:
        """Heuristic to identify character page links."""
        if not url:
            return False
        
        url_lower = url.lower()
        text_lower = link_text.lower() if link_text else ''
        
        # Check URL patterns
        if '/character' in url_lower or '/characters' in url_lower:
            return True
        
        # Check for character indicators in URL
        if any(indicator in url_lower for indicator in self.character_indicators):
            return True
        
        # Check text content for character indicators
        if any(indicator in text_lower for indicator in self.character_indicators):
            return True
        
        # Check for typical character name patterns (capitalized words)
        if link_text and len(link_text.split()) <= 3:  # Character names are usually 1-3 words
            words = link_text.split()
            if all(word[0].isupper() for word in words if word):  # All words start with capital
                return True
        
        return False
    
    def is_location_link(self, url: str, link_text: str) -> bool:
        """Heuristic to identify location page links."""
        if not url:
            return False
        
        url_lower = url.lower()
        text_lower = link_text.lower() if link_text else ''
        
        # Check URL patterns
        if '/location' in url_lower or '/locations' in url_lower or '/places' in url_lower:
            return True
        
        # Check for location indicators in URL or text
        if any(indicator in url_lower for indicator in self.location_indicators):
            return True
        
        if any(indicator in text_lower for indicator in self.location_indicators):
            return True
        
        return False
    
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