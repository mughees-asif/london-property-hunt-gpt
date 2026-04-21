from __future__ import annotations

from collections.abc import Iterable
from html.parser import HTMLParser

from property_hunt.collectors.base import BaseCollector, absolutize_url, clean_text
from property_hunt.models import ListingType, RawListing


class TextPlatformCollector(BaseCollector):
    def __init__(self, platform: str) -> None:
        self.platform = platform

    def parse_html(
        self, html: str, *, source_url: str, listing_type: ListingType
    ) -> Iterable[RawListing]:
        parser = ListingAnchorParser(source_url=source_url, platform=self.platform)
        parser.feed(html)
        listings: list[RawListing] = []
        seen: set[str] = set()
        for anchor in parser.anchors:
            url = anchor["url"]
            title = anchor["title"]
            if url in seen or not _looks_like_listing_url(url):
                continue
            seen.add(url)
            listings.append(
                RawListing(
                    platform=self.platform,
                    listing_type=listing_type,
                    source_url=source_url,
                    url=url,
                    title=title,
                    text=title,
                    data={"href": url, "anchor_text": title},
                )
            )
        return listings


class ListingAnchorParser(HTMLParser):
    def __init__(self, *, source_url: str, platform: str) -> None:
        super().__init__()
        self.source_url = source_url
        self.platform = platform
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = absolutize_url(self.source_url, href)
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._current_href:
            return
        title = clean_text(" ".join(self._current_text))
        if title:
            self.anchors.append({"url": self._current_href, "title": title})
        self._current_href = None
        self._current_text = []


def _looks_like_listing_url(url: str) -> bool:
    normalized = url.lower()
    tokens = (
        "/flatshare/",
        "/rooms/",
        "/room/",
        "/properties-to-rent/",
        "/property-to-rent/",
        "/to-rent/",
        "/flats-to-rent/",
    )
    return any(token in normalized for token in tokens)

