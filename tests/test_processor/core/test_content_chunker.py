"""
Tests for ContentChunker - splits wiki pages into semantic chunks for embedding.

Following TDD methodology: write tests first, then implement.
"""
import pytest
from typing import List, Dict, Any


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestContentChunkerInitialization:
    """Test ContentChunker initialization and configuration."""

    def test_init_with_default_params(self):
        """ContentChunker should initialize with default chunk size and overlap."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker()

        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50

    def test_init_with_custom_chunk_size(self):
        """ContentChunker should accept custom chunk size and overlap."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker(chunk_size=1000, chunk_overlap=100)

        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 100

    def test_init_validates_chunk_size(self):
        """ContentChunker should validate that chunk_size > chunk_overlap."""
        from src.processor.core.content_chunker import ContentChunker

        with pytest.raises(ValueError, match="chunk_size must be greater than chunk_overlap"):
            ContentChunker(chunk_size=100, chunk_overlap=150)

    def test_init_validates_positive_values(self):
        """ContentChunker should validate that chunk_size and overlap are positive."""
        from src.processor.core.content_chunker import ContentChunker

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            ContentChunker(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            ContentChunker(chunk_overlap=-10)


class TestContentChunkerChunking:
    """Test basic text chunking functionality."""

    def test_chunk_text_basic(self):
        """ContentChunker should split text into chunks of specified size."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker(chunk_size=50, chunk_overlap=10)
        text = "A" * 120  # 120 character string

        chunks = chunker.chunk_text(text)

        # Should create multiple chunks
        assert len(chunks) > 1
        # Each chunk should be approximately the right size (accounting for overlap)
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_chunk_text_preserves_sentences(self):
        """ContentChunker should try to preserve sentence boundaries when possible."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker(chunk_size=100, chunk_overlap=20)
        text = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."

        chunks = chunker.chunk_text(text)

        # Chunks should not split in the middle of words
        for chunk in chunks:
            # If chunk doesn't end at text boundary, it should end with sentence boundary or space
            if chunk != chunks[-1]:  # Last chunk might not end with period
                assert chunk.rstrip()[-1] in '.!? ' or chunk == text

    def test_chunk_text_with_overlap(self):
        """ContentChunker should create overlapping chunks for context."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker(chunk_size=50, chunk_overlap=10)
        text = "A" * 120

        chunks = chunker.chunk_text(text)

        # Adjacent chunks should overlap
        if len(chunks) > 1:
            # Check that end of first chunk overlaps with start of second
            overlap_region = chunks[0][-10:]
            assert chunks[1].startswith(overlap_region)

    def test_chunk_text_short_text(self):
        """ContentChunker should handle text shorter than chunk_size."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker(chunk_size=500, chunk_overlap=50)
        text = "Short text."

        chunks = chunker.chunk_text(text)

        # Should return single chunk
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_empty_text(self):
        """ContentChunker should handle empty text gracefully."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker()

        chunks = chunker.chunk_text("")

        # Should return empty list for empty text
        assert chunks == []


class TestContentChunkerPageProcessing:
    """Test chunking of wiki page JSON data."""

    def test_chunk_page_json(self):
        """ContentChunker should extract and chunk main_content from page JSON."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker(chunk_size=50, chunk_overlap=10)
        page_data = {
            "url": "https://example.com/wiki/Test",
            "content": {
                "title": "Test Page",
                "main_content": "A" * 120  # Content that will be chunked
            }
        }

        chunks = chunker.chunk_page(page_data)

        # Should return list of chunk dictionaries with metadata
        assert len(chunks) > 1
        assert all(isinstance(chunk, dict) for chunk in chunks)

        # Each chunk should have required metadata
        for i, chunk in enumerate(chunks):
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["url"] == page_data["url"]
            assert chunk["metadata"]["title"] == page_data["content"]["title"]
            assert chunk["metadata"]["chunk_index"] == i

    def test_chunk_page_adds_metadata(self):
        """ContentChunker should add source metadata to each chunk."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker()
        page_data = {
            "url": "https://avatar.fandom.com/wiki/Aang",
            "content": {
                "title": "Aang",
                "main_content": "Aang is the Avatar."
            }
        }

        chunks = chunker.chunk_page(page_data)

        chunk = chunks[0]
        assert chunk["text"] == "Aang is the Avatar."
        assert chunk["metadata"]["url"] == "https://avatar.fandom.com/wiki/Aang"
        assert chunk["metadata"]["title"] == "Aang"
        assert chunk["metadata"]["chunk_index"] == 0

    def test_chunk_multiple_pages(self):
        """ContentChunker should process multiple pages and maintain separate metadata."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker()
        pages = [
            {
                "url": "https://example.com/wiki/Page1",
                "content": {"title": "Page 1", "main_content": "Content for page 1"}
            },
            {
                "url": "https://example.com/wiki/Page2",
                "content": {"title": "Page 2", "main_content": "Content for page 2"}
            }
        ]

        all_chunks = chunker.chunk_pages(pages)

        # Should return chunks from both pages
        assert len(all_chunks) >= 2

        # Chunks from different pages should have different URLs
        urls = set(chunk["metadata"]["url"] for chunk in all_chunks)
        assert len(urls) == 2

    def test_chunk_page_missing_content(self):
        """ContentChunker should handle pages with missing main_content gracefully."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker()
        page_data = {
            "url": "https://example.com/wiki/Empty",
            "content": {
                "title": "Empty Page"
                # No main_content field
            }
        }

        chunks = chunker.chunk_page(page_data)

        # Should return empty list for page with no content
        assert chunks == []


class TestContentChunkerEdgeCases:
    """Test edge cases and error handling."""

    def test_chunk_text_with_unicode(self):
        """ContentChunker should handle Unicode characters correctly."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker()
        text = "Aang is the Avatar. 气 (qì) means air. Katara uses 水 (shuǐ)."

        chunks = chunker.chunk_text(text)

        # Should handle unicode without errors
        assert len(chunks) >= 1
        # Check that unicode characters are preserved
        all_text = "".join(chunks)
        assert "气" in all_text
        assert "水" in all_text

    def test_chunk_text_with_newlines(self):
        """ContentChunker should handle text with newlines."""
        from src.processor.core.content_chunker import ContentChunker

        chunker = ContentChunker()
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."

        chunks = chunker.chunk_text(text)

        # Should process text with newlines
        assert len(chunks) >= 1

    def test_chunk_text_prevents_infinite_loop(self):
        """
        ContentChunker should prevent infinite loops when sentence boundaries
        are very early in chunks.

        Regression test for bug where early sentence boundaries could cause
        start position to not advance, leading to infinite loop.
        """
        from src.processor.core.content_chunker import ContentChunker
        import time

        chunker = ContentChunker(chunk_size=500, chunk_overlap=50)

        # Create text with many short sentences that could trigger the bug
        text = "A. " * 2000  # 2000 very short sentences

        # This should complete quickly (not hang)
        start_time = time.time()
        chunks = chunker.chunk_text(text)
        elapsed = time.time() - start_time

        # Should complete in under 1 second for this small text
        assert elapsed < 1.0, f"Chunking took {elapsed}s - possible infinite loop"

        # Should produce chunks
        assert len(chunks) > 0

        # All chunks should be reasonable size
        for chunk in chunks:
            assert len(chunk) > 0, "Empty chunk detected"
            assert len(chunk) <= chunker.chunk_size + 100, "Chunk too large"
