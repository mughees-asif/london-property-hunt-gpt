from __future__ import annotations

import time
import urllib.request
from abc import ABC, abstractmethod
from html import unescape
from typing import Iterable
from urllib.parse import urljoin

from property_hunt.models import ListingType, RawListing


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


class BaseCollector(ABC):
    platform: str

    def collect_url(
        self, url: str, listing_type: ListingType, *, use_browser: bool
    ) -> list[RawListing]:
        html = fetch_html(url, use_browser=use_browser)
        return list(self.parse_html(html, source_url=url, listing_type=listing_type))

    @abstractmethod
    def parse_html(
        self, html: str, *, source_url: str, listing_type: ListingType
    ) -> Iterable[RawListing]:
        raise NotImplementedError


def fetch_html(url: str, *, use_browser: bool = False) -> str:
    if use_browser:
        browser_html = _fetch_html_with_playwright(url)
        if browser_html:
            return browser_html

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _fetch_html_with_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for --browser mode. Install dependencies and run "
            "`playwright install chromium`."
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=60_000)
        time.sleep(1)
        html = page.content()
        browser.close()
        return html


def absolutize_url(source_url: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    return urljoin(source_url, unescape(maybe_url))


def clean_text(value: object) -> str:
    text = unescape(str(value or ""))
    return " ".join(text.split())
