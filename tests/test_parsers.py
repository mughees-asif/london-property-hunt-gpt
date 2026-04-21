"""Parser fixture tests for JSON-backed platform collectors."""

from pathlib import Path

from property_hunt.collectors.rightmove import RightmoveCollector
from property_hunt.collectors.zoopla import ZooplaCollector
from property_hunt.models import ListingType


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_rightmove_next_data_parser() -> None:
    """Rightmove parser should read property URLs from __NEXT_DATA__."""

    html = (FIXTURES / "rightmove.html").read_text(encoding="utf-8")
    listings = list(
        RightmoveCollector().parse_html(
            html,
            source_url="https://www.rightmove.co.uk/property-to-rent/find.html",
            listing_type=ListingType.STUDIO,
        )
    )

    assert len(listings) == 1
    assert listings[0].url == "https://www.rightmove.co.uk/properties/123456"
    assert "Hackney" in listings[0].title


def test_zoopla_json_ld_parser() -> None:
    """Zoopla parser should read listing URLs from JSON-LD ItemList blocks."""

    html = (FIXTURES / "zoopla.html").read_text(encoding="utf-8")
    listings = list(
        ZooplaCollector().parse_html(
            html,
            source_url="https://www.zoopla.co.uk/to-rent/flats/london/",
            listing_type=ListingType.STUDIO,
        )
    )

    assert len(listings) == 1
    assert listings[0].url == "https://www.zoopla.co.uk/to-rent/details/abc"
    assert "Shoreditch" in listings[0].title
