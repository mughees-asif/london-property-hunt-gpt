from __future__ import annotations

import argparse

from property_hunt.config import load_config
from property_hunt.pipeline import run_pipeline
from property_hunt.tracker.xlsx import init_tracker


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="property-hunt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the property hunt workflow")
    run_parser.add_argument("--config", default="config.toml", help="Path to config TOML")
    run_parser.add_argument(
        "--browser", action="store_true", help="Use Playwright browser fetching"
    )
    run_parser.add_argument(
        "--no-gpt", action="store_true", help="Disable OpenAI extraction/outreach"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Collect and score without writing files"
    )
    run_parser.add_argument("--send", action="store_true", help="Send email when email.mode=smtp")

    init_parser = subparsers.add_parser("init-tracker", help="Create the tracker workbook")
    init_parser.add_argument("--config", default="config.toml", help="Path to config TOML")
    init_parser.add_argument("--force", action="store_true", help="Overwrite an existing tracker")

    show_parser = subparsers.add_parser("show-config", help="Print resolved important paths")
    show_parser.add_argument("--config", default="config.toml", help="Path to config TOML")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "run":
        result = run_pipeline(
            config,
            use_browser=args.browser,
            use_gpt=not args.no_gpt,
            dry_run=args.dry_run,
            send_email=args.send or config.email.send_by_default,
        )
        print(f"Raw listings: {result.raw_count}")
        print(f"Parsed listings: {result.parsed_count}")
        print(f"Added: {result.added_count}")
        print(f"Duplicates: {result.duplicate_count}")
        print(f"Skipped: {result.skipped_count}")
        print(f"Outreach files: {result.outreach_count}")
        if result.email_path:
            print(f"Email HTML: {result.email_path}")
        for warning in result.warnings:
            print(f"Warning: {warning}")
        return

    if args.command == "init-tracker":
        config.ensure_dirs()
        if config.paths.tracker_path.exists() and not args.force:
            raise SystemExit(f"Tracker already exists: {config.paths.tracker_path}")
        init_tracker(config.paths.tracker_path)
        print(f"Created tracker: {config.paths.tracker_path}")
        return

    if args.command == "show-config":
        print(f"Hunt dir: {config.paths.hunt_dir}")
        print(f"Tracker: {config.paths.tracker_path}")
        print(f"Outreach: {config.paths.outreach_dir}")
        print(f"Runs: {config.paths.run_dir}")
        print(f"Outbox: {config.paths.outbox_dir}")
        print(f"Search URLs: {len(config.search_urls)}")
        return
