"""
AtomToPubsub Configuration Module.

Uses Pydantic for type-safe configuration management.
Supports loading from environment variables and .env files.
"""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class FeedConfig(BaseModel):
    """Configuration for a single feed."""

    url: str = Field(..., description="URL to the Atom/RSS feed")
    server: str = Field(..., description="XMPP Pubsub server hostname")


class AtomToPubsubConfig(BaseModel):
    """Main configuration for AtomToPubsub."""

    # XMPP settings
    jid: str = Field(..., description="XMPP JID to post as")
    resource: str = Field(default="atomtopubsub", description="XMPP resource")
    secret: str = Field(..., description="XMPP password")

    # Feed settings
    feeds: dict[str, FeedConfig] = Field(default_factory=dict, description="Feed configurations")

    # Scheduler settings
    refresh_time: int = Field(default=60, ge=1, description="Refresh interval in minutes")

    # Cache settings
    cache_file: Path = Field(
        default_factory=lambda: Path("cache.pkl").resolve(),
        description="Path to cache file"
    )
    pid_file: Path = Field(
        default_factory=lambda: Path("/tmp/atomtopubsub.pid").resolve(),
        description="Path to PID file"
    )

    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")

    @classmethod
    def from_env(cls) -> "AtomToPubsubConfig":
        """Load configuration from environment variables."""
        env_config: dict[str, Any] = {}

        if os.getenv("XMPP_JID"):
            env_config["jid"] = os.getenv("XMPP_JID")
        if os.getenv("XMPP_SECRET"):
            env_config["secret"] = os.getenv("XMPP_SECRET")
        if os.getenv("XMPP_RESOURCE"):
            env_config["resource"] = os.getenv("XMPP_RESOURCE")
        if os.getenv("REFRESH_TIME"):
            env_config["refresh_time"] = int(os.getenv("REFRESH_TIME"))
        if os.getenv("LOG_LEVEL"):
            env_config["log_level"] = os.getenv("LOG_LEVEL")

        return cls(**env_config)

    def add_feed(self, name: str, url: str, server: str) -> None:
        """Add a feed to the configuration."""
        self.feeds[name] = FeedConfig(url=url, server=server)
