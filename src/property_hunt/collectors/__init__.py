"""Collector factory mapping configured platforms to @collectors implementations."""

from __future__ import annotations

from .base import BaseCollector
from .rightmove import RightmoveCollector
from .text_platform import TextPlatformCollector
from .zoopla import ZooplaCollector


def collector_for(platform: str) -> BaseCollector:
    """Return the parser/fetcher implementation for a platform name."""

    normalized = platform.lower()
    if normalized == "rightmove":
        return RightmoveCollector()
    if normalized == "zoopla":
        return ZooplaCollector()
    if normalized in {"openrent", "spareroom"}:
        return TextPlatformCollector(platform=normalized)
    raise ValueError(f"Unsupported platform: {platform}")
