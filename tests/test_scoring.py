from pathlib import Path

from property_hunt.config import load_config
from property_hunt.models import BillsIncluded, Furnished, Listing, ListingType, Priority
from property_hunt.scoring import score_listing


def _config():
    root = Path(__file__).resolve().parents[1]
    return load_config(root / "config.example.toml")


def test_room_in_four_bed_is_skipped() -> None:
    listing = Listing(
        title="Room in Hackney",
        platform="spareroom",
        url="https://example.com/a",
        listing_type=ListingType.ROOM,
        area="Hackney",
        price_pcm=1200,
        bills_included=BillsIncluded.YES,
        furnished=Furnished.YES,
        bed_count=4,
    )

    scored = score_listing(listing, _config())

    assert scored.priority == Priority.SKIP


def test_primary_area_room_within_budget_is_high() -> None:
    listing = Listing(
        title="Room in Hackney",
        platform="spareroom",
        url="https://example.com/b",
        listing_type=ListingType.ROOM,
        area="Hackney",
        price_pcm=1400,
        bills_included=BillsIncluded.YES,
        furnished=Furnished.YES,
        bed_count=3,
    )

    scored = score_listing(listing, _config())

    assert scored.priority == Priority.HIGH

