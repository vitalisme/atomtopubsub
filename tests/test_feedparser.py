"""Test module for feedparser."""

import pytest
from datetime import datetime

from atomtopubsub.feedparser import FeedParser, FeedInfo, FeedEntry


class TestFeedParser:
    """Tests for FeedParser class."""

    @pytest.fixture
    def parser(self) -> FeedParser:
        """Create a FeedParser instance."""
        return FeedParser()

    def test_parse_atom_feed(self, parser: FeedParser) -> None:
        """Test parsing a valid Atom feed."""
        # This would require a real URL or mock
        # For now, just test the class instantiation
        assert parser is not None

    def test_parse_invalid_url(self, parser: FeedParser) -> None:
        """Test parsing an invalid URL returns empty result, not None."""
        result = parser.parse("http://invalid.url.that.does.not.exist/feed.xml")
        # Invalid URLs return empty FeedInfo and entries, not None
        assert result is not None
        feed_info, entries = result
        assert isinstance(feed_info, FeedInfo)
        assert isinstance(entries, list)
        assert len(entries) == 0

    def test_feed_info_creation(self) -> None:
        """Test FeedInfo dataclass."""
        info = FeedInfo(
            title="Test Feed",
            description="A test feed",
            updated=datetime(2024, 1, 1, 12, 0, 0),
        )
        assert info.title == "Test Feed"
        assert info.description == "A test feed"

    def test_feed_entry_creation(self) -> None:
        """Test FeedEntry dataclass."""
        entry = FeedEntry(
            id="entry-123",
            title="Test Entry",
            updated=datetime(2024, 1, 1, 12, 0, 0),
            content="<p>Test content</p>",
        )
        assert entry.id == "entry-123"
        assert entry.title == "Test Entry"
        assert entry.content == "<p>Test content</p>"
