"""
Scheduler Module for AtomToPubsub.

Handles periodic feed parsing and publishing.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from time import struct_time

from apscheduler import schedulers
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from .config import AtomToPubsubConfig
from .feedparser import FeedParser, FeedInfo, FeedEntry
from .xmpp import Publishx


logger = logging.getLogger(__name__)


class CacheManager:
    """Manages the feed cache for tracking published entries."""

    def __init__(self, cache_file: Path) -> None:
        """Initialize cache manager."""
        self.cache_file = cache_file
        self._cache: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.debug("Loaded cache with %d entries", len(self._cache))
        except Exception as e:
            logger.warning("Failed to load cache: %s", e)
            self._cache = {}

    def save(self) -> None:
        """Save cache to file."""
        try:
            # Create parent directory if it doesn't exist
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, default=str)
            logger.debug("Cache saved")
        except Exception as e:
            logger.error("Failed to save cache: %s", e)

    def get_last_updated(self, feed_key: str) -> datetime | None:
        """Get the last update time for a feed."""
        if feed_key in self._cache:
            try:
                return datetime.fromisoformat(self._cache[feed_key])
            except (ValueError, TypeError):
                return None
        return None

    def set_last_updated(self, feed_key: str, updated: datetime) -> None:
        """Set the last update time for a feed."""
        self._cache[feed_key] = updated.isoformat()
        self.save()

    def is_entry_published(self, feed_key: str, entry: FeedEntry) -> bool:
        """Check if an entry has already been published."""
        cache_key = f"{feed_key}:{entry.id}"
        return cache_key in self._cache

    def mark_entry_published(self, feed_key: str, entry: FeedEntry) -> None:
        """Mark an entry as published."""
        cache_key = f"{feed_key}:{entry.id}"
        self._cache[cache_key] = datetime.utcnow().isoformat()
        self.save()

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache = {}
        self.save()


class FeedScheduler:
    """Scheduler for feed parsing and publishing."""

    def __init__(self, config: AtomToPubsubConfig) -> None:
        """Initialize the feed scheduler."""
        self.config = config
        self.feed_parser = FeedParser()
        self.cache = CacheManager(config.cache_file)
        self._scheduler = AsyncIOScheduler()
        self._xmpp: Publishx | None = None
        self._running = False

    async def start(self, xmpp: Publishx) -> None:
        """
        Start the scheduler.

        Args:
            xmpp: Connected XMPP client instance.
        """
        self._xmpp = xmpp
        self._running = True

        # Set up cache cleanup job
        self._scheduler.add_job(
            self.cache.clear,
            "interval",
            hours=16,
            id="cache_cleanup",
        )

        # Set up scheduler listener
        self._scheduler.add_listener(
            self._on_job_event,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
        )

        # Start scheduler
        self._scheduler.start()
        logger.info("Scheduler started")

        # Start feed polling
        asyncio.create_task(self._poll_feeds())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        self._scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def _poll_feeds(self) -> None:
        """Poll all feeds periodically."""
        feed_items = list(self.config.feeds.items())
        refresh_interval = self.config.refresh_time / len(feed_items) if feed_items else 1

        while self._running:
            for feed_key, feed_config in feed_items:
                if not self._running:
                    break

                logger.info("Parsing feed: %s", feed_key)
                try:
                    await self._process_feed(feed_key, feed_config.url, feed_config.server)
                except Exception as e:
                    logger.error("Error processing feed %s: %s", feed_key, e)

                # Wait before next feed
                await asyncio.sleep(refresh_interval * 60)

    async def _process_feed(self, feed_key: str, url: str, server: str) -> None:
        """Process a single feed."""
        if not self._xmpp:
            logger.error("XMPP client not connected")
            return

        result = self.feed_parser.parse(url)
        if not result:
            logger.error("Failed to parse feed %s: %s", feed_key, self.feed_parser.last_error)
            return

        feed_info, entries = result

        # Ensure node exists
        await self._xmpp.create_node(server, feed_key, feed_info)

        # Process entries
        last_updated = self.cache.get_last_updated(feed_key)

        for entry in reversed(entries):
            # Check if entry is new
            should_publish = (
                last_updated is None
                or entry.updated > last_updated
                or not self.cache.is_entry_published(feed_key, entry)
            )

            if should_publish:
                logger.info("Publishing new entry: %s", entry.title)
                version = getattr(entry, "_version", "atom10")
                success = await self._xmpp.publish_entry(server, feed_key, entry, version)

                if success:
                    self.cache.mark_entry_published(feed_key, entry)
            else:
                logger.debug("Skipping already published entry: %s", entry.title)

        # Update last updated time
        if feed_info.updated:
            self.cache.set_last_updated(feed_key, feed_info.updated)

    def _on_job_event(self, event: Any) -> None:
        """Handle scheduler job events."""
        if event.exception:
            logger.error("Job %s crashed: %s", event.job_id, event.exception)
        else:
            logger.debug("Job %s executed successfully", event.job_id)
