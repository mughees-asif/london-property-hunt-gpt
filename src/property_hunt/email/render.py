"""HTML summary rendering for the final @pipeline output."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

from property_hunt.config import AppConfig
from property_hunt.models import Listing, Priority


def render_summary_email(
    *,
    config: AppConfig,
    added: list[Listing],
    duplicates: list[Listing],
    skipped: list[Listing],
    outreach_count: int,
) -> str:
    """Render an actionable HTML summary from tracker write results."""

    counts = Counter(listing.priority.value for listing in added)
    platform_counts = Counter(listing.platform for listing in added)
    title = f"London Property Hunt - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    high = [listing for listing in added if listing.priority == Priority.HIGH]
    medium = [listing for listing in added if listing.priority == Priority.MEDIUM]
    low = [listing for listing in added if listing.priority == Priority.LOW]

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
</head>
<body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.4;">
  <h1>{escape(title)}</h1>
  <p>
    <strong>New:</strong> {len(added)} |
    <strong>Duplicates:</strong> {len(duplicates)} |
    <strong>Skipped:</strong> {len(skipped)} |
    <strong>Outreach files:</strong> {outreach_count}
  </p>
  <p>
    <strong>High:</strong> {counts.get("High", 0)} |
    <strong>Medium:</strong> {counts.get("Medium", 0)} |
    <strong>Low:</strong> {counts.get("Low", 0)}
  </p>
  <p><strong>Platforms:</strong> {_counter_text(platform_counts)}</p>
  {_section("High Priority", high, include_message=True)}
  {_section("Medium Priority", medium, include_message=True)}
  {_section("Low Priority", low, include_message=False)}
  {_skipped_section(skipped)}
  <p style="margin-top: 24px;">
    Move-in target: {escape(config.profile.move_in_date.isoformat())}.
    Message at least 5 suitable listings today.
  </p>
</body>
</html>
"""


def write_email_file(config: AppConfig, html: str) -> Path:
    """Persist rendered HTML to the configured outbox directory."""

    filename = f"property-hunt-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"
    path = config.paths.outbox_dir / filename
    path.write_text(html, encoding="utf-8")
    return path


def _section(title: str, listings: list[Listing], *, include_message: bool) -> str:
    """Render a priority section with listing cards."""

    if not listings:
        return f"<h2>{escape(title)}</h2><p>No listings.</p>"
    cards = "\n".join(
        _listing_card(listing, include_message=include_message) for listing in listings
    )
    return f"<h2>{escape(title)}</h2>{cards}"


def _listing_card(listing: Listing, *, include_message: bool) -> str:
    """Render one listing card for the email body."""

    message = ""
    if include_message and listing.outreach_message:
        message = (
            '<div style="background:#eef8ee;border:1px solid #b7dfb7;'
            'padding:10px;margin-top:8px;">'
            f"{escape(listing.outreach_message)}"
            "</div>"
        )
    price = f"GBP {listing.price_pcm} pcm" if listing.price_pcm else "Price unknown"
    return f"""
  <div style="border:1px solid #d1d5db; padding:12px; margin:10px 0;">
    <h3 style="margin:0 0 6px 0;"><a href="{escape(listing.url)}">{escape(listing.title)}</a></h3>
    <p style="margin:0;">
      {escape(listing.area or "Area unknown")} |
      {escape(price)} |
      {escape(listing.platform)} |
      {escape(listing.available_from or "Availability unknown")}
    </p>
    <p style="margin:6px 0 0 0;">{escape(listing.notes)}</p>
    {message}
  </div>
"""


def _skipped_section(skipped: list[Listing]) -> str:
    """Render skipped listings as a compact list."""

    if not skipped:
        return "<h2>Skipped</h2><p>No skipped listings.</p>"
    items = "\n".join(
        f'<li><a href="{escape(listing.url)}">{escape(listing.title)}</a> '
        f"- {escape(listing.notes)}</li>"
        for listing in skipped
    )
    return f"<h2>Skipped</h2><ul>{items}</ul>"


def _counter_text(counter: Counter[str]) -> str:
    """Format a Counter for human-readable email stats."""

    if not counter:
        return "none"
    return ", ".join(f"{key}: {value}" for key, value in sorted(counter.items()))
