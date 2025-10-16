"""
ContentChunker - splits wiki pages into semantic chunks for embedding.

This module handles splitting large wiki pages into smaller chunks that can be
embedded and stored in a vector database for semantic search.
"""
from typing import List, Dict, Any, Optional
import re


class ContentChunker:
    """
    Splits text content into overlapping chunks for embedding.

    Args:
        chunk_size: Maximum characters per chunk (default: 500)
        chunk_overlap: Characters of overlap between consecutive chunks (default: 50)

    Raises:
        ValueError: If chunk_size <= chunk_overlap or if values are invalid
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        """Initialize ContentChunker with specified chunk parameters."""
        # Validate inputs
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_size <= chunk_overlap:
            raise ValueError("chunk_size must be greater than chunk_overlap")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks, preserving sentence boundaries when possible.

        Args:
            text: Input text to chunk

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # If text is shorter than chunk size, return as single chunk
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            # Calculate end position for this chunk
            end = start + self.chunk_size

            # If this is not the last chunk, try to break at sentence boundary
            if end < len(text):
                # Look for sentence boundaries (., !, ?) in the last portion of chunk
                chunk_text = text[start:end]

                # Try to find last sentence boundary
                sentence_end_match = None
                for match in re.finditer(r'[.!?]\s', chunk_text):
                    sentence_end_match = match

                # If we found a sentence boundary, use it
                if sentence_end_match:
                    end = start + sentence_end_match.end()
                # Otherwise, try to break at last space to avoid splitting words
                elif ' ' in chunk_text:
                    last_space = chunk_text.rfind(' ')
                    if last_space > 0:  # Make sure we don't create empty chunks
                        end = start + last_space + 1

            # Extract chunk
            chunk = text[start:end]
            chunks.append(chunk)

            # Move start position forward, accounting for overlap
            if end >= len(text):
                break

            # Ensure we always make progress (prevent infinite loops)
            new_start = end - self.chunk_overlap
            if new_start <= start:
                # If overlap would cause us to go backwards, just move forward minimally
                new_start = start + max(1, self.chunk_size // 2)

            start = new_start

        return chunks

    def chunk_page(self, page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk a wiki page and add rich contextual metadata to each chunk.

        Args:
            page_data: Wiki page data with structure:
                {
                    "url": "https://...",
                    "content": {
                        "title": "Page Title",
                        "main_content": "text content...",
                        "namespace": "optional namespace",
                        ...
                    }
                }

        Returns:
            List of chunk dictionaries with format:
                {
                    "text": "chunk text",
                    "metadata": {
                        "url": "source url",
                        "title": "page title",
                        "chunk_index": 0,
                        "total_chunks": N,
                        "namespace": "namespace if available",
                        "char_start": start position in original text,
                        "char_end": end position in original text
                    }
                }
        """
        # Extract main content
        content = page_data.get("content", {})
        main_content = content.get("main_content", "")

        if not main_content:
            return []

        # Extract metadata
        url = page_data.get("url", "")
        title = content.get("title", "")
        namespace = content.get("namespace")

        # Chunk the text
        text_chunks = self.chunk_text(main_content)

        # Add metadata to each chunk with contextual information
        chunks_with_metadata = []
        char_position = 0

        for i, text in enumerate(text_chunks):
            # Calculate character positions in original text
            char_start = char_position
            char_end = char_start + len(text)
            char_position = char_end - self.chunk_overlap  # Account for overlap

            # Build metadata
            metadata = {
                "url": url,
                "title": title,
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "char_start": char_start,
                "char_end": char_end
            }

            # Add optional contextual fields if available
            if namespace:
                metadata["namespace"] = namespace

            chunk_dict = {
                "text": text,
                "metadata": metadata
            }
            chunks_with_metadata.append(chunk_dict)

        return chunks_with_metadata

    def chunk_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk multiple wiki pages.

        Args:
            pages: List of page data dictionaries

        Returns:
            List of all chunks from all pages with metadata
        """
        all_chunks = []
        for page in pages:
            chunks = self.chunk_page(page)
            all_chunks.extend(chunks)
        return all_chunks
