from __future__ import annotations

import json
import re
from collections.abc import Iterable
from html import unescape
from typing import Any

from property_hunt.collectors.base import BaseCollector, absolutize_url, clean_text
from property_hunt.models import ListingType, RawListing


class ZooplaCollector(BaseCollector):
    platform = "zoopla"

    def parse_html(
        self, html: str, *, source_url: str, listing_type: ListingType
    ) -> Iterable[RawListing]:
        payloads = extract_json_ld(html)
        listings: list[RawListing] = []
        seen: set[str] = set()

        for payload in payloads:
            for element in _iter_item_list_elements(payload):
                item = element.get("item", element)
                url = absolutize_url(source_url, str(item.get("url") or ""))
                if not url or url in seen:
                    continue
                seen.add(url)
                listings.append(
                    RawListing(
                        platform=self.platform,
                        listing_type=listing_type,
                        source_url=source_url,
                        url=url,
                        title=clean_text(item.get("name") or item.get("description")),
                        text=clean_text(item.get("description")),
                        data=item,
                    )
                )
        return listings


def extract_json_ld(html: str) -> list[dict[str, Any]]:
    blocks = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    payloads: list[dict[str, Any]] = []
    for block in blocks:
        try:
            decoded = json.loads(unescape(block))
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            payloads.append(decoded)
        elif isinstance(decoded, list):
            payloads.extend(item for item in decoded if isinstance(item, dict))
    return payloads


def _iter_item_list_elements(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    elements = payload.get("itemListElement", [])
    if isinstance(elements, dict):
        elements = [elements]
    if isinstance(elements, list):
        for element in elements:
            if isinstance(element, dict):
                yield element

