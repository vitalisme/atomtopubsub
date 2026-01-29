"""Test module for config."""

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from atomtopubsub.config import AtomToPubsubConfig, FeedConfig


class TestConfig:
    """Tests for configuration module."""

    def test_feed_config_creation(self) -> None:
        """Test creating a FeedConfig."""
        feed = FeedConfig(
            url="https://example.com/feed",
            server="pubsub.example.com",
        )
        assert feed.url == "https://example.com/feed"
        assert feed.server == "pubsub.example.com"

    def test_main_config_defaults(self) -> None:
        """Test default configuration values."""
        config = AtomToPubsubConfig(
            jid="test@example.com",
            secret="password",
        )
        assert config.resource == "atomtopubsub"
        assert config.refresh_time == 60
        assert config.log_level == "INFO"
        assert len(config.feeds) == 0

    def test_add_feed(self) -> None:
        """Test adding feeds."""
        config = AtomToPubsubConfig(
            jid="test@example.com",
            secret="password",
        )
        config.add_feed("TestFeed", "https://example.com/feed", "pubsub.example.com")
        assert "TestFeed" in config.feeds

    def test_jid_required(self) -> None:
        """Test that JID is required."""
        with pytest.raises(ValidationError):
            AtomToPubsubConfig(secret="password")

    def test_from_env(self) -> None:
        """Test loading from environment variables."""
        import os
        os.environ["XMPP_JID"] = "env@example.com"
        os.environ["XMPP_SECRET"] = "env-password"
        os.environ["REFRESH_TIME"] = "30"

        try:
            config = AtomToPubsubConfig.from_env()
            assert config.jid == "env@example.com"
            assert config.secret == "env-password"
            assert config.refresh_time == 30
        finally:
            del os.environ["XMPP_JID"]
            del os.environ["XMPP_SECRET"]
            del os.environ["REFRESH_TIME"]

    def test_config_json_serialization(self) -> None:
        """Test configuration can be serialized to JSON."""
        config = AtomToPubsubConfig(
            jid="test@example.com",
            secret="password",
        )
        config.add_feed("TestFeed", "https://example.com/feed", "pubsub.example.com")

        json_str = config.model_dump_json(indent=2)
        assert "test@example.com" in json_str
        assert "TestFeed" in json_str
