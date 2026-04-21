"""TOML config loading for @cli and dependency injection into @pipeline."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .models import ListingType


@dataclass(frozen=True)
class ProfileConfig:
    """Tenant profile values used by @llm.outreach and @email."""

    name: str
    age: int
    profession: str
    profile_description: str
    profile_summary: str
    work_postcode: str
    move_in_date: date


@dataclass(frozen=True)
class CriteriaConfig:
    """Search and scoring rules consumed by @scoring."""

    primary_areas: tuple[str, ...]
    secondary_areas: tuple[str, ...]
    room_budget: int
    room_budget_no_bills: int
    studio_budget: int
    flatmate_min_age: int
    flatmate_max_age: int
    skip_student_households: bool


@dataclass(frozen=True)
class PathsConfig:
    """Resolved local output paths for tracker, run reports, and summaries."""

    hunt_dir: Path
    tracker_path: Path
    outreach_dir: Path
    run_dir: Path
    outbox_dir: Path


@dataclass(frozen=True)
class OpenAIConfig:
    """OpenAI model settings for @llm.extract and @llm.outreach."""

    model: str
    reasoning_effort: str
    enable_extraction: bool
    enable_outreach: bool


@dataclass(frozen=True)
class EmailConfig:
    """Email delivery settings used by @email.render and @email.gmail."""

    to: str
    from_address: str
    mode: str
    send_by_default: bool


@dataclass(frozen=True)
class SearchUrl:
    """One configured platform search endpoint."""

    platform: str
    listing_type: ListingType
    url: str


@dataclass(frozen=True)
class AppConfig:
    """Fully resolved application configuration passed through the workflow."""

    profile: ProfileConfig
    criteria: CriteriaConfig
    paths: PathsConfig
    openai: OpenAIConfig
    email: EmailConfig
    search_urls: tuple[SearchUrl, ...]

    def ensure_dirs(self) -> None:
        """Create all local output directories required by a run."""

        self.paths.hunt_dir.mkdir(parents=True, exist_ok=True)
        self.paths.outreach_dir.mkdir(parents=True, exist_ok=True)
        self.paths.run_dir.mkdir(parents=True, exist_ok=True)
        self.paths.outbox_dir.mkdir(parents=True, exist_ok=True)


def load_config(path: str | Path) -> AppConfig:
    """Load a TOML file into typed config objects."""

    config_path = Path(path).expanduser()
    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)

    profile = payload["profile"]
    criteria = payload["criteria"]
    paths = payload["paths"]
    openai = payload.get("openai", {})
    email = payload.get("email", {})
    hunt_dir = Path(str(paths["hunt_dir"])).expanduser()

    tracker_path = hunt_dir / str(paths.get("tracker_filename", "london_room_hunt.xlsx"))
    search_url_payloads = payload.get("search", {}).get("urls", [])
    search_urls = tuple(_parse_search_url(item) for item in search_url_payloads)
    if not search_urls:
        raise ValueError("At least one [[search.urls]] entry is required")

    return AppConfig(
        profile=ProfileConfig(
            name=str(profile["name"]),
            age=int(profile["age"]),
            profession=str(profile["profession"]),
            profile_description=str(profile["profile_description"]),
            profile_summary=str(profile["profile_summary"]),
            work_postcode=str(profile["work_postcode"]),
            move_in_date=_parse_date(profile["move_in_date"]),
        ),
        criteria=CriteriaConfig(
            primary_areas=tuple(str(value) for value in criteria.get("primary_areas", [])),
            secondary_areas=tuple(str(value) for value in criteria.get("secondary_areas", [])),
            room_budget=int(criteria["room_budget"]),
            room_budget_no_bills=int(criteria.get("room_budget_no_bills", criteria["room_budget"])),
            studio_budget=int(criteria["studio_budget"]),
            flatmate_min_age=int(criteria.get("flatmate_min_age", 0)),
            flatmate_max_age=int(criteria.get("flatmate_max_age", 99)),
            skip_student_households=bool(criteria.get("skip_student_households", True)),
        ),
        paths=PathsConfig(
            hunt_dir=hunt_dir,
            tracker_path=tracker_path,
            outreach_dir=hunt_dir / str(paths.get("outreach_dir", "outreach")),
            run_dir=hunt_dir / str(paths.get("run_dir", "runs")),
            outbox_dir=hunt_dir / str(paths.get("outbox_dir", "outbox")),
        ),
        openai=OpenAIConfig(
            model=str(openai.get("model", "gpt-5.4")),
            reasoning_effort=str(openai.get("reasoning_effort", "low")),
            enable_extraction=bool(openai.get("enable_extraction", True)),
            enable_outreach=bool(openai.get("enable_outreach", True)),
        ),
        email=EmailConfig(
            to=str(email.get("to", "")),
            from_address=str(email.get("from_address", email.get("to", ""))),
            mode=str(email.get("mode", "html_file")),
            send_by_default=bool(email.get("send_by_default", False)),
        ),
        search_urls=search_urls,
    )


def _parse_search_url(item: dict[str, Any]) -> SearchUrl:
    """Parse a single [[search.urls]] entry."""

    return SearchUrl(
        platform=str(item["platform"]).strip().lower(),
        listing_type=ListingType(str(item["listing_type"]).strip().lower()),
        url=str(item["url"]).strip(),
    )


def _parse_date(value: Any) -> date:
    """Parse TOML-native or ISO date values."""

    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
