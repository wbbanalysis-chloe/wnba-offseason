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

# Every box-score input to Game Score, summed per player-season.
COMPONENTS = [
    "points",
    "field_goals_made",
    "field_goals_attempted",
    "free_throws_made",
    "free_throws_attempted",
    "offensive_rebounds",
    "defensive_rebounds",
    "assists",
    "steals",
    "blocks",
    "fouls",
    "turnovers",
]


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


def played(box):
    """Rows that count as a game played (docs/decisions.md 2026-10-06).

    Zero-minute rows stay in: ESPN rounds minutes to whole numbers, so a brief
    appearance shows as 0. Null minutes on a non-DNP row is an inactive-roster row.
    """
    return box[~box["did_not_play"].astype(bool) & box["minutes"].notna()]


def aggregate_player_seasons(box):
    """Sum games, minutes, and Game Score components per (season, athlete_id)."""
    rows = played(box).assign(game_date=lambda d: pd.to_datetime(d["game_date"]))
    rows = rows.sort_values(["game_date", "game_id"])
    grouped = rows.groupby(["season", "athlete_id"], sort=True)

    out = grouped[["minutes"] + COMPONENTS].sum()
    out.insert(0, "games_played", grouped["game_id"].nunique())
    out.insert(0, "player_name", grouped["athlete_display_name"].last())
    # Rows are date-sorted, so unique() gives teams in order of first appearance.
    out["teams"] = grouped["team_display_name"].agg(lambda names: list(names.unique()))
    out["n_teams"] = out["teams"].str.len()
    return out.reset_index()


def add_rates(df):
    """Add Game Score (Hollinger), Game Score per 40, and TS% from season totals."""
    df = df.copy()
    df["game_score"] = (
        df["points"]
        + 0.4 * df["field_goals_made"]
        - 0.7 * df["field_goals_attempted"]
        - 0.4 * (df["free_throws_attempted"] - df["free_throws_made"])
        + 0.7 * df["offensive_rebounds"]
        + 0.3 * df["defensive_rebounds"]
        + df["steals"]
        + 0.7 * df["assists"]
        + 0.7 * df["blocks"]
        - 0.4 * df["fouls"]
        - df["turnovers"]
    )
    # Per 40 because a WNBA game is 40 minutes. where() turns a zero denominator
    # into null instead of inf.
    minutes = df["minutes"].where(df["minutes"] > 0)
    df["game_score_per40"] = df["game_score"] / minutes * 40
    shooting_possessions = 2 * (df["field_goals_attempted"] + 0.44 * df["free_throws_attempted"])
    df["ts_pct"] = df["points"] / shooting_possessions.where(shooting_possessions > 0)
    return df
