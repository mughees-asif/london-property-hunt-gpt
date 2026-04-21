from __future__ import annotations

import json
import re
from typing import Any

from property_hunt.config import AppConfig
from property_hunt.llm.client import response_text
from property_hunt.models import BillsIncluded, Furnished, Listing, ListingType, RawListing


def listing_from_raw(raw: RawListing, config: AppConfig, *, use_gpt: bool) -> Listing:
    baseline = heuristic_listing(raw, config)
    if not use_gpt or not config.openai.enable_extraction:
        return baseline

    try:
        payload = extract_with_gpt(raw, config)
    except RuntimeError:
        return baseline

    merged = baseline.__dict__.copy()
    for key, value in payload.items():
        if value not in (None, ""):
            merged[key] = value
    merged["platform"] = raw.platform
    merged["listing_type"] = raw.listing_type.value
    merged["url"] = raw.url or merged.get("url") or ""
    return Listing.from_dict(merged)


def extract_with_gpt(raw: RawListing, config: AppConfig) -> dict[str, Any]:
    system = (
        "You extract UK rental listing data. Return only JSON. "
        "Do not invent missing values. Use ISO dates only when explicit."
    )
    user = json.dumps(
        {
            "platform": raw.platform,
            "listing_type": raw.listing_type.value,
            "source_url": raw.source_url,
            "url": raw.url,
            "title": raw.title,
            "text": raw.text,
            "data": raw.data,
            "schema": {
                "title": "string",
                "url": "string",
                "area": "string",
                "postcode": "string",
                "price_pcm": "integer or null",
                "bills_included": "Yes, No, or Unknown",
                "available_from": "YYYY-MM-DD or empty string",
                "furnished": "Yes, No, or Unknown",
                "bed_count": "integer or null",
                "flatmates": "string",
                "contact": "string",
                "notes": "string",
            },
            "rules": [
                "For room listings, bed_count means total bedrooms in the property.",
                "If a value is not explicit, use Unknown, null, or empty string.",
                "Never infer contact details.",
            ],
        },
        ensure_ascii=True,
    )
    text = response_text(config.openai, system=system, user=user)
    return _parse_json_object(text)


def heuristic_listing(raw: RawListing, config: AppConfig) -> Listing:
    data = raw.data or {}
    text = " ".join(
        value
        for value in [
            raw.title or "",
            raw.text or "",
            json.dumps(data, ensure_ascii=True, default=str)[:4000],
        ]
        if value
    )

    return Listing(
        title=raw.title or _first_string(data, ("title", "heading", "displayAddress", "name"))
        or "Untitled listing",
        platform=raw.platform,
        url=raw.url or _first_string(data, ("url", "propertyUrl", "listingUrl")) or "",
        listing_type=raw.listing_type,
        area=_guess_area(text, config),
        postcode=_guess_postcode(text),
        price_pcm=_guess_price(data, text),
        bills_included=_guess_bills(text),
        available_from="",
        furnished=_guess_furnished(text),
        bed_count=_guess_beds(data, text, raw.listing_type),
        flatmates=_guess_flatmates(text),
        notes="",
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return parsed


def _first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def _guess_area(text: str, config: AppConfig) -> str:
    normalized = text.lower()
    for area in (*config.criteria.primary_areas, *config.criteria.secondary_areas):
        if area.lower() in normalized:
            return area
    return ""


def _guess_postcode(text: str) -> str:
    match = re.search(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b", text, flags=re.I)
    return match.group(0).upper() if match else ""


def _guess_price(data: dict[str, Any], text: str) -> int | None:
    for key in ("price_pcm", "price", "amount", "rent"):
        value = data.get(key)
        if isinstance(value, dict):
            value = value.get("amount") or value.get("value")
        parsed = _money_to_int(value)
        if parsed:
            return parsed

    display_prices = data.get("displayPrices")
    if isinstance(display_prices, list) and display_prices:
        parsed = _money_to_int(display_prices[0])
        if parsed:
            return parsed

    match = re.search(r"(?:£|GBP\s*)\s*([0-9][0-9,]{2,5})", text, flags=re.I)
    return int(match.group(1).replace(",", "")) if match else None


def _money_to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        return _money_to_int(value.get("amount") or value.get("value") or value.get("displayPrice"))
    text = str(value).replace(",", "")
    match = re.search(r"([0-9]{3,6})", text)
    return int(match.group(1)) if match else None


def _guess_beds(data: dict[str, Any], text: str, listing_type: ListingType) -> int | None:
    for key in ("bed_count", "bedrooms", "numberOfBedrooms", "beds"):
        value = data.get(key)
        if isinstance(value, int):
            return value
        if value is not None and str(value).isdigit():
            return int(value)
    if listing_type == ListingType.STUDIO and "studio" in text.lower():
        return 0
    match = re.search(r"\b([1-9])\s*(?:bed|bedroom|bedrooms)\b", text, flags=re.I)
    return int(match.group(1)) if match else None


def _guess_bills(text: str) -> BillsIncluded:
    normalized = text.lower()
    if "bills included" in normalized or "including bills" in normalized:
        return BillsIncluded.YES
    if "bills not included" in normalized or "excluding bills" in normalized:
        return BillsIncluded.NO
    return BillsIncluded.UNKNOWN


def _guess_furnished(text: str) -> Furnished:
    normalized = text.lower()
    if "unfurnished" in normalized:
        return Furnished.NO
    if "furnished" in normalized:
        return Furnished.YES
    return Furnished.UNKNOWN


def _guess_flatmates(text: str) -> str:
    lower = text.lower()
    if "student" in lower:
        return "student signal"
    if "professional" in lower:
        return "professional signal"
    return ""

