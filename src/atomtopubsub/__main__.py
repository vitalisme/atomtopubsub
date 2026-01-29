#!/usr/bin/env python3
"""
Main entry point for AtomToPubsub.

Usage:
    atomtopubsub --config CONFIG_FILE
    atomtopubsub --jid jid@example.com --secret password --refresh 60
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from .config import AtomToPubsubConfig
from .scheduler import FeedScheduler
from .xmpp import Publishx


logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    """Configure logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Parse Atom feeds and publish to XMPP Pubsub nodes."
    )
    parser.add_argument(
        "--config", "-c", type=Path, help="Path to configuration file"
    )
    parser.add_argument(
        "--jid", "-j", help="XMPP JID (format: user@server.tld)"
    )
    parser.add_argument(
        "--secret", "-s", help="XMPP password"
    )
    parser.add_argument(
        "--resource", "-r", default="atomtopubsub", help="XMPP resource"
    )
    parser.add_argument(
        "--refresh", type=int, default=60, help="Refresh interval in minutes"
    )
    parser.add_argument(
        "--log-level", "-l", default="INFO", help="Logging level"
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 2.0.0"
    )

    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> int:
    """Main async entry point."""
    # Load configuration
    if args.config and args.config.exists():
        config = AtomToPubsubConfig.model_validate_json(args.config.read_text())
    elif args.jid and args.secret:
        config = AtomToPubsubConfig(
            jid=args.jid,
            secret=args.secret,
            resource=args.resource,
            refresh_time=args.refresh,
        )
    else:
        # Try loading from environment
        config = AtomToPubsubConfig.from_env()

    # Setup logging
    setup_logging(args.log_level if hasattr(args, "log_level") else "INFO")

    logger.info("Starting AtomToPubsub v2.0.0")
    logger.info("Connecting to XMPP as %s", config.jid)

    # Create XMPP client
    xmpp = Publishx(config)

    # Connect
    xmpp.connect()

    # Create scheduler
    scheduler = FeedScheduler(config)

    # Handle session start
    async def on_session_start(_: Any) -> None:
        logger.info("XMPP session started")
        await scheduler.start(xmpp)

    xmpp.add_event_handler("session_start", on_session_start)

    # Run forever - wait for shutdown signal
    shutdown_event = asyncio.Event()

    try:
        await shutdown_event.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await scheduler.stop()
    finally:
        xmpp.disconnect()

    return 0


def main() -> int:
    """Main entry point."""
    args = parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
