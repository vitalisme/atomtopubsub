"""
Feed Parser Module for AtomToPubsub.

Handles parsing of Atom 1.0, RSS 2.0, and Atom 0.3 feeds.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from time import struct_time
from typing import Any
import socket

import feedparser
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 15
# Maximum retry attempts
MAX_RETRIES = 2


def _struct_time_to_datetime(value: Any) -> datetime | None:
    """Convert struct_time to datetime, or return None."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, struct_time):
        return datetime(*value[:6])
    return None


@dataclass
class FeedEntry:
    """Represents a parsed feed entry."""

    id: str
    title: str
    updated: datetime
    content: str | None = None
    description: str | None = None
    links: list[dict[str, str]] | None = None
    tags: list[str] | None = None
    authors: list[dict[str, str]] | None = None


@dataclass
class FeedInfo:
    """Represents parsed feed metadata."""

    title: str
    description: str | None = None
    logo: str | None = None
    updated: datetime | None = None


class FeedParser:
    """Parser for Atom and RSS feeds."""

    NS_ATOM = "http://www.w3.org/2005/Atom"
    NS_XHTML = "http://www.w3.org/1999/xhtml"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES) -> None:
        """Initialize the feed parser."""
        self._last_error: str | None = None
        self._last_error_type: str | None = None
        self._timeout = timeout
        self._max_retries = max_retries
        self._error_count: dict[str, int] = {}

    @property
    def last_error(self) -> str | None:
        """Get the last error message."""
        return self._last_error

    @property
    def last_error_type(self) -> str | None:
        """Get the last error type."""
        return self._last_error_type

    @property
    def error_count(self) -> dict[str, int]:
        """Get error count per feed."""
        return self._error_count.copy()

    def reset_error_count(self, url: str | None = None) -> None:
        """Reset error count for a specific URL or all feeds."""
        if url:
            if url in self._error_count:
                del self._error_count[url]
        else:
            self._error_count.clear()

    def parse(self, url: str) -> tuple[FeedInfo, list[FeedEntry]] | None:
        """
        Parse a feed from the given URL with timeout and retry support.

        Args:
            url: URL to the feed.
            timeout: Request timeout in seconds (default: 15).
            max_retries: Maximum retry attempts (default: 2).

        Returns:
            Tuple of FeedInfo and list of FeedEntry, or None on error.
        """
        import urllib.error

        last_exception: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                parsed = self._fetch_with_timeout(url, attempt)
                break
            except (socket.timeout, urllib.error.URLError, urllib.error.HTTPError) as e:
                last_exception = e
                self._error_count[url] = self._error_count.get(url, 0) + 1
                logger.warning(
                    "Attempt %d/%d failed for %s: %s - %s",
                    attempt,
                    self._max_retries,
                    url,
                    type(e).__name__,
                    str(e),
                )
                if attempt < self._max_retries:
                    logger.info("Retrying in %d seconds...", self._timeout)
                continue
            except Exception as e:
                last_exception = e
                logger.error("Unexpected error fetching %s: %s", url, e)
                self._last_error = str(e)
                self._last_error_type = type(e).__name__
                return None
        else:
            # All retries exhausted
            error_type = type(last_exception).__name__ if last_exception else "Unknown"
            error_msg = str(last_exception) if last_exception else "Unknown error"
            logger.error(
                "All %d attempts failed for %s. Last error: %s - %s",
                self._max_retries,
                url,
                error_type,
                error_msg,
            )
            self._last_error = error_msg
            self._last_error_type = error_type
            return None

        # Reset error count on success
        if url in self._error_count:
            del self._error_count[url]

        if parsed.bozo:
            logger.warning("XML parsing error for %s", url)
            if hasattr(parsed.bozo_exception, "getMessage"):
                logger.warning("Bozo exception: %s", parsed.bozo_exception.getMessage())

        feed_info = self._parse_feed_info(parsed.feed)
        entries = [self._parse_entry(entry) for entry in parsed.entries]

        logger.debug("Successfully parsed %s: %d entries", url, len(entries))
        return feed_info, entries

    def _fetch_with_timeout(self, url: str, attempt: int) -> Any:
        """Fetch feed with timeout support."""
        socket.setdefaulttimeout(self._timeout)
        parsed = feedparser.parse(url)
        return parsed

    def _parse_feed_info(self, feed: Any) -> FeedInfo:
        """Parse feed metadata."""
        title = getattr(feed, "title", "") or ""
        description: str | None = getattr(feed, "description", None)
        if not description:
            description = getattr(feed, "subtitle", None)
        logo: str | None = getattr(feed, "logo", None)
        updated: datetime | None = _struct_time_to_datetime(getattr(feed, "updated_parsed", None))
        return FeedInfo(title=title, description=description, logo=logo, updated=updated)

    def _parse_entry(self, entry: Any) -> FeedEntry:
        """Parse a single feed entry."""
        entry_id = getattr(entry, "id", "") or getattr(entry, "link", "")
        title = getattr(entry, "title", "") or "Untitled"
        updated = _struct_time_to_datetime(getattr(entry, "updated_parsed", None)) or datetime.utcnow()
        content: str | None = None
        description: str | None = None

        version = getattr(entry, "version", "")

        if version == "rss20" or "rss10" in str(version):
            # Prioritize content:encoded (used by Substack and many other feeds)
            if hasattr(entry, "content_encoded") and entry.content_encoded:
                content = self._parse_html_content(entry.content_encoded)
                logger.debug("Found content in content_encoded for: %s", title[:50])
            elif hasattr(entry, "content") and entry.content:
                content = self._parse_html_content(entry.content[0].value)
                logger.debug("Found content in content for: %s", title[:50])
            elif hasattr(entry, "summary") and entry.summary:
                # Use summary as fallback (often contains full content)
                content = self._parse_html_content(entry.summary)
                logger.debug("Found content in summary for: %s", title[:50])
            elif hasattr(entry, "description") and entry.description:
                description = entry.description
                logger.debug("Only description for: %s", title[:50])
        elif version == "atom03":
            if hasattr(entry, "content"):
                content = self._parse_atom_content(entry.content)
        elif version == "atom10":
            if hasattr(entry, "content"):
                content = self._parse_html_content(entry.content[0].value)
            elif hasattr(entry, "summary") and entry.summary:
                content = self._parse_html_content(entry.summary)
            elif hasattr(entry, "description"):
                description = entry.description

        # Additional fallback: check for any content field
        if not content and hasattr(entry, "summary") and entry.summary:
            content = self._parse_html_content(entry.summary)

        links: list[dict[str, str]] = []
        if hasattr(entry, "links"):
            for link in entry.links:
                link_dict: dict[str, str] = {}
                if hasattr(link, "href"):
                    link_dict["href"] = link.href
                if hasattr(link, "type"):
                    link_dict["type"] = link.type
                if hasattr(link, "rel"):
                    link_dict["rel"] = link.rel
                links.append(link_dict)

        tags: list[str] = []
        if hasattr(entry, "tags"):
            for tag in entry.tags:
                tags.append(tag.term)

        authors: list[dict[str, str]] = []
        if hasattr(entry, "authors"):
            for author in entry.authors:
                author_dict: dict[str, str] = {"name": getattr(author, "name", "")}
                if hasattr(author, "href"):
                    author_dict["href"] = author.href
                authors.append(author_dict)
        elif hasattr(entry, "author"):
            authors.append({"name": entry.author})

        return FeedEntry(
            id=entry_id,
            title=title,
            updated=updated,
            content=content,
            description=description,
            links=links,
            tags=tags,
            authors=authors,
        )

    def _parse_html_content(self, html_content: str) -> str:
        """Parse and clean HTML content."""
        try:
            soup = BeautifulSoup(html_content, "html5lib")
            return soup.prettify()
        except Exception:
            return html_content

    def _parse_atom_content(self, content: list[Any]) -> str:
        """Parse Atom content element."""
        if not content:
            return ""

        try:
            soup = BeautifulSoup(content[0].value, "html.parser")
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()
            content_value = soup.prettify()
            if not content_value.strip().startswith("<div"):
                content_value = f'<div xmlns="{self.NS_XHTML}">\n{content_value}\n</div>'
            return content_value
        except Exception:
            return str(content[0].value) if content else ""
