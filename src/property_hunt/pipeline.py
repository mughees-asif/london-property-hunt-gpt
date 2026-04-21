"""End-to-end orchestration from @collectors to @tracker and @email."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from property_hunt.collectors import collector_for
from property_hunt.config import AppConfig
from property_hunt.email.gmail import send_smtp
from property_hunt.email.render import render_summary_email, write_email_file
from property_hunt.llm.extract import listing_from_raw
from property_hunt.llm.outreach import save_outreach_files
from property_hunt.models import Listing, Priority, RawListing
from property_hunt.scoring import score_listing
from property_hunt.tracker.xlsx import TrackerResult, append_new_listings


@dataclass(frozen=True)
class RunResult:
    """Small CLI-facing summary of one workflow execution."""

    raw_count: int
    parsed_count: int
    added_count: int
    duplicate_count: int
    skipped_count: int
    outreach_count: int
    email_path: Path | None
    warnings: tuple[str, ...]


def run_pipeline(
    config: AppConfig,
    *,
    use_browser: bool,
    use_gpt: bool,
    dry_run: bool,
    send_email: bool,
) -> RunResult:
    """Run collection, extraction, scoring, persistence, outreach, and summary output."""

    config.ensure_dirs()
    warnings: list[str] = []
    raw_listings = collect_raw_listings(config, use_browser=use_browser, warnings=warnings)
    parsed = [
        score_listing(listing_from_raw(raw, config, use_gpt=use_gpt), config)
        for raw in raw_listings
    ]
    skipped = [listing for listing in parsed if listing.priority == Priority.SKIP]
    trackable = [listing for listing in parsed if listing.is_trackable]

    tracker_result = TrackerResult(added=trackable, duplicates=[])
    outreach_count = 0
    email_path: Path | None = None

    if not dry_run:
        tracker_result = append_new_listings(config.paths.tracker_path, trackable)
        outreach_count = save_outreach_files(tracker_result.added, config, use_gpt=use_gpt)
        html = render_summary_email(
            config=config,
            added=tracker_result.added,
            duplicates=tracker_result.duplicates,
            skipped=skipped,
            outreach_count=outreach_count,
        )
        if config.email.mode == "smtp" and send_email:
            send_smtp(config, subject="London Property Hunt", html=html)
        else:
            email_path = write_email_file(config, html)
        _write_run_report(
            config, parsed, tracker_result, skipped, outreach_count, warnings, email_path
        )

    return RunResult(
        raw_count=len(raw_listings),
        parsed_count=len(parsed),
        added_count=len(tracker_result.added),
        duplicate_count=len(tracker_result.duplicates),
        skipped_count=len(skipped),
        outreach_count=outreach_count,
        email_path=email_path,
        warnings=tuple(warnings),
    )


def collect_raw_listings(
    config: AppConfig, *, use_browser: bool, warnings: list[str]
) -> list[RawListing]:
    """Collect raw listings from all configured search URLs."""

    collected: list[RawListing] = []
    for search_url in config.search_urls:
        try:
            collector = collector_for(search_url.platform)
            collected.extend(
                collector.collect_url(
                    search_url.url, search_url.listing_type, use_browser=use_browser
                )
            )
        except Exception as exc:
            warnings.append(f"{search_url.platform}: {exc}")
    return collected


def _write_run_report(
    config: AppConfig,
    parsed: list[Listing],
    tracker_result: TrackerResult,
    skipped: list[Listing],
    outreach_count: int,
    warnings: list[str],
    email_path: Path | None,
) -> None:
    """Persist a machine-readable JSON report for audit/debugging."""

    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "parsed_count": len(parsed),
        "added_count": len(tracker_result.added),
        "duplicate_count": len(tracker_result.duplicates),
        "skipped_count": len(skipped),
        "outreach_count": outreach_count,
        "email_path": str(email_path) if email_path else None,
        "warnings": warnings,
        "added": [_listing_report_item(listing) for listing in tracker_result.added],
        "skipped": [_listing_report_item(listing) for listing in skipped],
    }
    path = config.paths.run_dir / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")


def _listing_report_item(listing: Listing) -> dict[str, object]:
    """Serialise one listing into the run-report shape."""

    return {
        "title": listing.title,
        "platform": listing.platform,
        "url": listing.url,
        "area": listing.area,
        "price_pcm": listing.price_pcm,
        "priority": listing.priority.value,
        "notes": listing.notes,
    }
