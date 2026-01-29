"""
XMPP Pubsub Client Module for AtomToPubsub.

Handles connection to XMPP server and publishing to Pubsub nodes.
"""

import logging
import re
from datetime import datetime
from typing import Any

from slixmpp import ClientXMPP
from slixmpp.exceptions import IqError, IqTimeout, XMPPError
from slixmpp.plugins.xep_0060.stanza.pubsub import Item
from slixmpp.xmlstream import ET

from .config import AtomToPubsubConfig
from .feedparser import FeedParser, FeedInfo, FeedEntry

logger = logging.getLogger(__name__)

# XML namespace constants
NS_ATOM = "http://www.w3.org/2005/Atom"
NS_JABBER_DATA = "jabber:x:data"


class Publishx(ClientXMPP):
    """XMPP client for publishing to Pubsub nodes."""

    def __init__(self, config: AtomToPubsubConfig) -> None:
        """Initialize the XMPP client."""
        full_jid = f"{config.jid}/{config.resource}"
        super().__init__(full_jid, config.secret)

        self.config = config
        self._feed_parser = FeedParser()

        # Register plugins
        self.register_plugin("xep_0060")  # Pubsub

    async def create_node(self, server: str, node: str, feed_info: FeedInfo) -> bool:
        """
        Create a Pubsub node if it doesn't exist.

        Args:
            server: XMPP server hostname.
            node: Node identifier.
            feed_info: Feed metadata for node configuration.

        Returns:
            True if node was created or already exists.
        """
        logger.info("Creating node %s on %s", node, server)

        iq = self.Iq(stype="set", sto=server)
        iq["pubsub"]["create"]["node"] = node

        # Configure node
        form = iq["pubsub"]["configure"]["form"]
        form["type"] = "submit"
        form.addField("pubsub#type", ftype="text-single", value="urn:xmpp:pubsub-social-feed:1")
        form.addField("pubsub#persist_items", ftype="boolean", value=1)
        form.addField("pubsub#notify_retract", ftype="boolean", value=1)
        form.addField("pubsub#title", ftype="text-single", value=feed_info.title)
        form.addField("pubsub#max_items", ftype="text-single", value="max")
        form.addField("pubsub#send_last_published_item", ftype="text-single", value="never")
        form.addField("pubsub#deliver_payloads", ftype="boolean", value=0)
        if feed_info.description:
            form.addField("pubsub#description", ftype="text-single", value=feed_info.description)

        # Check if node exists
        try:
            await self.plugin["xep_0060"].get_node_config(server, node)
            logger.info("Node %s already exists", node)
            return True
        except XMPPError:
            pass

        # Create node
        try:
            await iq.send(timeout=5)
            logger.info("Node %s created successfully", node)
            return True
        except (IqError, IqTimeout) as e:
            logger.error("Failed to create node %s: %s", node, e)
            return False

    async def publish_entry(
        self, server: str, node: str, entry: FeedEntry, version: str
    ) -> bool:
        """
        Publish a single entry to a Pubsub node.

        Args:
            server: XMPP server hostname.
            node: Node identifier.
            entry: Feed entry to publish.
            version: Feed version (atom10, rss20, atom03).

        Returns:
            True if published successfully.
        """
        try:
            iq = self.Iq(stype="set", sto=server)
            iq["pubsub"]["publish"]["node"] = node

            # Create entry item
            item = Item()
            # Sanitize ID (replace problematic characters)
            rex = re.compile(r"[:,\/]")
            item["id"] = rex.sub("-", str(entry.id))

            # Build Atom entry
            ent = ET.Element("entry")
            ent.set("xmlns", NS_ATOM)

            # Title
            title = ET.SubElement(ent, "title")
            title.text = entry.title

            # Updated timestamp
            updated = ET.SubElement(ent, "updated")
            updated.text = entry.updated.isoformat() if isinstance(entry.updated, datetime) else str(entry.updated)

            # Content
            if entry.content:
                self._add_content_to_entry(ent, entry.content, "text/html", version)
            elif entry.description:
                self._add_content_to_entry(ent, entry.description, "text/html", version)

            # Links
            if entry.links:
                for link in entry.links:
                    link_elem = ET.SubElement(ent, "link")
                    if href := link.get("href"):
                        link_elem.set("href", href)
                    if link_type := link.get("type"):
                        link_elem.set("type", link_type)
                    if rel := link.get("rel"):
                        link_elem.set("rel", rel)

            # Tags/categories
            if entry.tags:
                for tag in entry.tags:
                    cat = ET.SubElement(ent, "category")
                    cat.set("term", tag)

            # Authors
            if entry.authors:
                self._add_author_to_entry(ent, entry.authors[0], version)

            item["payload"] = ent
            iq["pubsub"]["publish"].append(item)

            # Send
            await iq.send(timeout=5)
            logger.debug("Published entry %s to %s/%s", entry.id, server, node)
            return True

        except (IqError, IqTimeout) as e:
            logger.error("Failed to publish entry %s: %s", entry.id, e)
            return False

    def _add_content_to_entry(
        self, entry_elem: ET.Element, content: str, content_type: str, version: str
    ) -> None:
        """Add content element to entry."""
        if version == "atom03":
            content_elem = ET.SubElement(entry_elem, "content")
            content_elem.set("type", "xhtml")
            content_elem.text = content
        else:
            content_elem = ET.SubElement(entry_elem, "content")
            content_elem.set("type", content_type)
            content_elem.text = content

    def _add_author_to_entry(
        self, entry_elem: ET.Element, author: dict[str, str], version: str
    ) -> None:
        """Add author element to entry."""
        author_elem = ET.SubElement(entry_elem, "author")
        name_elem = ET.SubElement(author_elem, "name")
        name_elem.text = author.get("name", "")

        if href := author.get("href"):
            uri_elem = ET.SubElement(author_elem, "uri")
            uri_elem.text = href
