"""Build data/clean/player_seasons.parquet: one row per WNBA player-season.

Source: sportsdataverse wehoop-wnba-data parquet releases (player_box, schedules,
player_core). Every filter and measure definition here is an approved entry in
docs/decisions.md — change the decision log first, then this file.

Run: python pipeline/build.py
"""

from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd

SEASONS = range(2015, 2027)

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

RELEASE_BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
# file stem -> release tag. Stems are what upstream names the per-season files.
DATASETS = {
    "player_box": "espn_wnba_player_boxscores",
    "wnba_schedule": "espn_wnba_schedules",
    "player_core": "espn_wnba_player_core",
}

REGULAR_SEASON = 2  # season_type; 3 is postseason

# All-Star rosters: "TEAM CLARK", "Team Delle Donne", ... (casing varies by year),
# and plain EAST/WEST in 2015 and 2017. See docs/decisions.md 2026-10-06.
ALL_STAR_TEAM_PATTERN = r"(?i)^team\s"
ALL_STAR_CONFERENCE_NAMES = {"EAST", "WEST"}

# The 2021 Commissioner's Cup final (Storm vs. Sun, 2021-08-12) carries the
# group-play note instead of the "Championship" one, so it can't be found by
# headline. Evidence in docs/decisions.md 2026-10-06: both teams show 33 games
# against the league's 32.
CUP_CHAMPIONSHIP_OVERRIDES = {401353913}


def download_raw(seasons=SEASONS, raw_dir=RAW_DIR):
    """Fetch each season's parquet files into data/raw/, skipping ones already there."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for stem, tag in DATASETS.items():
        for season in seasons:
            target = raw_dir / f"{stem}_{season}.parquet"
            if not target.exists():
                urlretrieve(f"{RELEASE_BASE}/{tag}/{target.name}", target)


def load_dataset(stem, seasons=SEASONS, raw_dir=RAW_DIR):
    """Read one dataset's per-season parquet files into a single frame."""
    frames = [pd.read_parquet(Path(raw_dir) / f"{stem}_{season}.parquet") for season in seasons]
    return pd.concat(frames, ignore_index=True)


def excluded_game_ids(box, schedules):
    """game_ids tagged regular season that don't count: All-Star and Cup Championship."""
    names = box["team_display_name"]
    is_all_star_team = names.str.match(ALL_STAR_TEAM_PATTERN) | names.str.upper().isin(
        ALL_STAR_CONFERENCE_NAMES
    )
    headline = schedules["notes_headline"].fillna("")
    is_noted = headline.str.contains("all-star", case=False) | headline.str.contains(
        "commissioner's cup championship", case=False
    )
    excluded = (
        set(box.loc[is_all_star_team, "game_id"])
        | set(schedules.loc[is_noted, "game_id"])
        | CUP_CHAMPIONSHIP_OVERRIDES
    )
    return excluded & set(box["game_id"])


def filter_regular_season(box, excluded):
    """Keep regular-season rows, minus the excluded games."""
    keep = (box["season_type"] == REGULAR_SEASON) & ~box["game_id"].isin(excluded)
    return box[keep].reset_index(drop=True)
