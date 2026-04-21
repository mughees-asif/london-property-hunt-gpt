from __future__ import annotations

import re
from pathlib import Path

from property_hunt.config import AppConfig
from property_hunt.llm.client import response_text
from property_hunt.models import Listing, Priority


def generate_outreach(listing: Listing, config: AppConfig, *, use_gpt: bool) -> str:
    if use_gpt and config.openai.enable_outreach:
        try:
            return _generate_with_gpt(listing, config)
        except RuntimeError:
            pass
    return fallback_outreach(listing, config)


def save_outreach_files(listings: list[Listing], config: AppConfig, *, use_gpt: bool) -> int:
    count = 0
    for listing in listings:
        if listing.priority != Priority.HIGH:
            continue
        message = generate_outreach(listing, config, use_gpt=use_gpt)
        listing.outreach_message = message
        filename = _outreach_filename(listing)
        path = config.paths.outreach_dir / filename
        path.write_text(message + "\n", encoding="utf-8")
        count += 1
    return count


def fallback_outreach(listing: Listing, config: AppConfig) -> str:
    detail = listing.area or "the listing"
    price = f" at GBP {listing.price_pcm} pcm" if listing.price_pcm else ""
    return (
        f"Hi, I liked {detail}{price}. I'm {config.profile.name}, "
        f"{config.profile.age}, a {config.profile.profession}. "
        f"{config.profile.profile_summary}. I'm looking to move around "
        f"{config.profile.move_in_date.isoformat()} and would be happy to arrange a viewing. "
        f"Thanks, {config.profile.name}"
    )


def _generate_with_gpt(listing: Listing, config: AppConfig) -> str:
    system = (
        "Write concise UK rental outreach messages. "
        "Return only the message text. Keep it under 100 words."
    )
    user = (
        f"Tenant: {config.profile.name}, {config.profile.age}, {config.profile.profession}. "
        f"Profile: {config.profile.profile_summary}. "
        f"Move-in: {config.profile.move_in_date.isoformat()}. "
        f"Listing: title={listing.title!r}, area={listing.area!r}, "
        f"price={listing.price_pcm!r}, available={listing.available_from!r}, "
        f"notes={listing.notes!r}. Mention one specific listing detail if available."
    )
    return response_text(config.openai, system=system, user=user).strip()


def _outreach_filename(listing: Listing) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{listing.platform}-{listing.area}-{listing.title}".lower())
    slug = slug.strip("-")[:90] or "listing"
    return f"outreach-{slug}.txt"


def list_outreach_files(outreach_dir: Path) -> list[Path]:
    return sorted(outreach_dir.glob("outreach-*.txt"))

