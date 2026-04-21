"""Rightmove parser that extracts listing candidates from __NEXT_DATA__ JSON."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from html import unescape
from typing import Any

from property_hunt.collectors.base import BaseCollector, absolutize_url, clean_text
from property_hunt.models import ListingType, RawListing


class RightmoveCollector(BaseCollector):
    """Collector for Rightmove search-result pages."""

    platform = "rightmove"

    def parse_html(
        self, html: str, *, source_url: str, listing_type: ListingType
    ) -> Iterable[RawListing]:
        """Walk embedded Next.js state and return property-like objects."""

        payload = extract_next_data(html)
        if not payload:
            return []

        listings: list[RawListing] = []
        seen: set[str] = set()
        for item in walk_dicts(payload):
            url = (
                item.get("propertyUrl")
                or item.get("listingUrl")
                or item.get("url")
                or item.get("detailUrl")
            )
            absolute_url = absolutize_url(source_url, str(url)) if url else None
            if not absolute_url or "rightmove" not in absolute_url or absolute_url in seen:
                continue

            seen.add(absolute_url)
            title = (
                item.get("displayAddress")
                or item.get("address")
                or item.get("heading")
                or item.get("title")
            )
            listings.append(
                RawListing(
                    platform=self.platform,
                    listing_type=listing_type,
                    source_url=source_url,
                    url=absolute_url,
                    title=clean_text(title),
                    text=clean_text(item.get("summary") or item.get("description")),
                    data=item,
                )
            )
        return listings


def extract_next_data(html: str) -> dict[str, Any] | None:
    """Extract the embedded Next.js JSON payload from a Rightmove page."""

    match = re.search(
        r"<script[^>]+id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(unescape(match.group(1)))
    except json.JSONDecodeError:
        return None


def walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    """Yield every dict in a nested JSON-like structure."""

    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)
