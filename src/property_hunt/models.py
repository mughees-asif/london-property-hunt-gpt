"""Shared listing and enum models consumed by @collectors, @scoring, and @tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class ListingType(str, Enum):
    """Supported rental search categories."""

    ROOM = "room"
    STUDIO = "studio"


class Priority(str, Enum):
    """Scoring outcomes used by @scoring and persisted by @tracker."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    SKIP = "Skip"


class BillsIncluded(str, Enum):
    """Normalised bills-included state for tracker and email output."""

    YES = "Yes"
    NO = "No"
    UNKNOWN = "Unknown"


class Furnished(str, Enum):
    """Normalised furnishing state for ranking and tracker output."""

    YES = "Yes"
    NO = "No"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class RawListing:
    """Raw platform payload emitted by @collectors before GPT/heuristic extraction."""

    platform: str
    listing_type: ListingType
    source_url: str
    url: str | None = None
    title: str | None = None
    text: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Listing:
    """Canonical listing record passed through @scoring, @tracker, and @email."""

    title: str
    platform: str
    url: str
    listing_type: ListingType
    area: str = ""
    postcode: str = ""
    price_pcm: int | None = None
    bills_included: BillsIncluded = BillsIncluded.UNKNOWN
    available_from: str = ""
    furnished: Furnished = Furnished.UNKNOWN
    bed_count: int | None = None
    flatmates: str = ""
    contact: str = ""
    notes: str = ""
    status: str = "NEW"
    priority: Priority = Priority.LOW
    found_on: str = field(default_factory=lambda: date.today().isoformat())
    outreach_message: str = ""

    @property
    def canonical_url(self) -> str:
        """Return the URL form used for deduplication."""

        return canonicalize_url(self.url)

    @property
    def is_trackable(self) -> bool:
        """Return whether the listing should be persisted in @tracker."""

        return bool(self.url) and self.priority != Priority.SKIP

    def to_tracker_row(self) -> list[Any]:
        """Convert the listing into the XLSX row order expected by @tracker.xlsx."""

        bed_value: Any = self.bed_count
        if self.listing_type == ListingType.STUDIO and bed_value is None:
            bed_value = "Studio/1-Bed"
        return [
            self.title,
            self.platform,
            self.url,
            self.area,
            self.postcode,
            self.price_pcm,
            self.bills_included.value,
            self.available_from,
            self.furnished.value,
            bed_value,
            self.flatmates,
            self.contact,
            self.notes,
            self.status,
            self.priority.value,
            self.found_on,
        ]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Listing:
        """Build a listing from GPT or report payloads with defensive coercion."""

        listing_type = ListingType(str(payload.get("listing_type", "room")).lower())
        priority_raw = str(payload.get("priority", Priority.LOW.value)).title()
        priority = (
            Priority(priority_raw)
            if priority_raw in Priority._value2member_map_
            else Priority.LOW
        )
        return cls(
            title=str(payload.get("title") or "Untitled listing").strip(),
            platform=str(payload.get("platform") or "").strip(),
            url=str(payload.get("url") or "").strip(),
            listing_type=listing_type,
            area=str(payload.get("area") or "").strip(),
            postcode=str(payload.get("postcode") or "").strip(),
            price_pcm=_int_or_none(payload.get("price_pcm")),
            bills_included=_enum_or_default(
                BillsIncluded, payload.get("bills_included"), BillsIncluded.UNKNOWN
            ),
            available_from=str(payload.get("available_from") or "").strip(),
            furnished=_enum_or_default(Furnished, payload.get("furnished"), Furnished.UNKNOWN),
            bed_count=_int_or_none(payload.get("bed_count")),
            flatmates=str(payload.get("flatmates") or "").strip(),
            contact=str(payload.get("contact") or "").strip(),
            notes=str(payload.get("notes") or "").strip(),
            status=str(payload.get("status") or "NEW").strip(),
            priority=priority,
            found_on=str(payload.get("found_on") or date.today().isoformat()).strip(),
            outreach_message=str(payload.get("outreach_message") or "").strip(),
        )


def canonicalize_url(url: str) -> str:
    """Strip tracking params and normalise casing for URL dedupe."""

    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "msclkid"}
    ]
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def _int_or_none(value: Any) -> int | None:
    """Coerce loose numeric values from platform/GPT payloads."""

    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).replace(",", "")
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def _enum_or_default(enum_type: type[Enum], value: Any, default: Enum) -> Any:
    """Map external enum-like strings to known enum members."""

    if value is None:
        return default
    normalized = str(value).strip().title()
    for member in enum_type:
        if member.value == normalized:
            return member
    return default
