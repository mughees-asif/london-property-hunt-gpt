"""Config loader tests for @property_hunt.config."""

from pathlib import Path

from property_hunt.config import load_config


def test_load_example_config() -> None:
    """The example TOML should load into the typed config tree."""

    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config.example.toml")

    assert config.profile.name == "Alex"
    assert config.criteria.room_budget == 1500
    assert len(config.search_urls) == 5
    assert config.paths.tracker_path.name == "london_room_hunt.xlsx"
