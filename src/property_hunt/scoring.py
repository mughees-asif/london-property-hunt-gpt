from __future__ import annotations

from datetime import date, timedelta

from .config import AppConfig
from .models import BillsIncluded, Furnished, Listing, ListingType, Priority


YOUNG_OR_STUDENT_TERMS = (
    "student",
    "students",
    "under 25",
    "under-25",
    "18-25",
    "party",
    "young household",
)


def score_listing(listing: Listing, config: AppConfig) -> Listing:
    notes: list[str] = []

    if listing.listing_type == ListingType.ROOM:
        priority = _score_room(listing, config, notes)
    else:
        priority = _score_studio(listing, config, notes)

    listing.priority = priority
    if notes:
        listing.notes = _append_notes(listing.notes, notes)
    return listing


def _score_room(listing: Listing, config: AppConfig, notes: list[str]) -> Priority:
    text = f"{listing.title} {listing.flatmates} {listing.notes}".lower()
    if listing.bed_count is not None and listing.bed_count >= 4:
        notes.append("Skipped: room listing is in a 4+ bedroom property")
        return Priority.SKIP

    if listing.bed_count is None:
        notes.append("Verify bed count before messaging")

    if config.criteria.skip_student_households and any(
        term in text for term in YOUNG_OR_STUDENT_TERMS
    ):
        notes.append("Skipped or downgraded: student/young household signal")
        return Priority.SKIP

    budget = (
        config.criteria.room_budget
        if listing.bills_included == BillsIncluded.YES
        else config.criteria.room_budget_no_bills
    )
    budget_ok = listing.price_pcm is not None and listing.price_pcm <= budget
    if not budget_ok:
        notes.append("Over budget or price unknown")

    area_tier = _area_tier(listing.area, config)
    available_ok = _available_by_target(listing.available_from, config.profile.move_in_date)
    furnished_ok = listing.furnished != Furnished.NO

    if area_tier == "primary" and budget_ok and available_ok and furnished_ok:
        return Priority.HIGH
    if budget_ok and area_tier in {"primary", "secondary"}:
        return Priority.MEDIUM
    return Priority.LOW


def _score_studio(listing: Listing, config: AppConfig, notes: list[str]) -> Priority:
    budget_ok = listing.price_pcm is not None and listing.price_pcm <= config.criteria.studio_budget
    if not budget_ok:
        notes.append("Over studio budget or price unknown")

    area_tier = _area_tier(listing.area, config)
    available_ok = _available_by_target(listing.available_from, config.profile.move_in_date)
    furnished_ok = listing.furnished != Furnished.NO

    if area_tier == "primary" and budget_ok and available_ok and furnished_ok:
        return Priority.HIGH
    if budget_ok and area_tier in {"primary", "secondary"}:
        return Priority.MEDIUM
    return Priority.LOW


def _area_tier(area: str, config: AppConfig) -> str:
    area_normalized = area.lower()
    if any(candidate.lower() in area_normalized for candidate in config.criteria.primary_areas):
        return "primary"
    if any(candidate.lower() in area_normalized for candidate in config.criteria.secondary_areas):
        return "secondary"
    return "other"


def _available_by_target(value: str, target: date) -> bool:
    if not value:
        return True
    try:
        available = date.fromisoformat(value[:10])
    except ValueError:
        return True
    return available <= target + timedelta(days=7)


def _append_notes(existing: str, notes: list[str]) -> str:
    if not existing:
        return "; ".join(notes)
    return f"{existing}; {'; '.join(notes)}"
