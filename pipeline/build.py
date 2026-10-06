"""Build data/clean/player_seasons.parquet: one row per WNBA player-season.

Source: sportsdataverse wehoop-wnba-data parquet releases (player_box, schedules,
player_core). Every filter and measure definition here is an approved entry in
docs/decisions.md — change the decision log first, then this file.

Run: python pipeline/build.py
"""

import ssl
from pathlib import Path
from urllib.request import urlopen

import certifi
import pandas as pd

SEASONS = range(2015, 2027)

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_PATH = REPO_ROOT / "data" / "clean" / "player_seasons.parquet"
# Birth dates verified by hand where player_core contradicts itself across seasons.
DOB_OVERRIDES_PATH = Path(__file__).resolve().parent / "dob_overrides.csv"

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

# A player on the floor every minute has exactly 0.2 of her team's player-minutes.
# The tolerance covers ESPN's whole-number minutes not always summing to 200 a game.
MAX_TEAM_MINUTES_SHARE = 0.2
SHARE_ROUNDING_TOLERANCE = 0.005

# A missing birth date is acceptable below this many season minutes; at or above
# it the date has to be looked up (docs/decisions.md 2026-10-06).
AGE_REQUIRED_MINUTES = 200

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
    # certifi's CA bundle, because python.org's macOS Python ships without one
    # and fails certificate checks out of the box.
    context = ssl.create_default_context(cafile=certifi.where())
    for stem, tag in DATASETS.items():
        for season in seasons:
            target = raw_dir / f"{stem}_{season}.parquet"
            if not target.exists():
                with urlopen(f"{RELEASE_BASE}/{tag}/{target.name}", context=context) as response:
                    target.write_bytes(response.read())


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


def add_team_shares(df, box):
    """Add share of team minutes and share of team games (docs/decisions.md 2026-10-06).

    Denominator for a one-team player is the team's whole season. For a player with
    more than one team it is, per stint, only that team's games from her first to
    last box row of the stint — any row counts, including did-not-play, because a
    row means she was on the roster.
    """
    key = ["season", "athlete_id"]
    rows = box.assign(game_date=pd.to_datetime(box["game_date"]))

    team_games = rows.groupby(["season", "team_id", "game_id"], as_index=False).agg(
        game_date=("game_date", "first"), team_minutes=("minutes", "sum")
    )

    # A stint is a run of consecutive rows with the same team, so a player who
    # returns to a former team gets two windows rather than one spanning both.
    rows = rows.sort_values(key + ["game_date", "game_id"])
    new_stint = rows["team_id"] != rows.groupby(key)["team_id"].shift()
    rows["stint"] = new_stint.groupby([rows["season"], rows["athlete_id"]]).cumsum()
    stints = rows.groupby(key + ["stint", "team_id"], as_index=False).agg(
        first_date=("game_date", "min"), last_date=("game_date", "max")
    )
    stints["whole_season"] = stints.groupby(key)["team_id"].transform("nunique") == 1

    windowed = stints.merge(team_games, on=["season", "team_id"])
    in_window = windowed["whole_season"] | windowed["game_date"].between(
        windowed["first_date"], windowed["last_date"]
    )
    available = (
        windowed[in_window]
        .groupby(key, as_index=False)
        .agg(team_minutes=("team_minutes", "sum"), team_games=("game_id", "nunique"))
    )

    df = df.merge(available, on=key, how="left", validate="one_to_one")
    df["team_minutes_share"] = df["minutes"] / df["team_minutes"]
    df["team_games_share"] = df["games_played"] / df["team_games"]
    return df.drop(columns=["team_minutes", "team_games"])


def resolve_birth_dates(core, overrides):
    """One birth date per athlete_id, as a Series indexed by athlete_id.

    player_core has one file per season and three players' dates differ between
    files. A conflict is never settled by picking a file: it needs a verified row
    in dob_overrides.csv, or the build stops (docs/decisions.md 2026-10-06).
    """
    known = core.dropna(subset=["date_of_birth"])
    # Upstream format is "1987-08-21T07:00Z" (midnight US Pacific in UTC); the
    # first ten characters are the calendar date.
    dates = pd.to_datetime(known["date_of_birth"].str[:10]).groupby(known["athlete_id"])
    verified = pd.to_datetime(overrides.set_index("athlete_id")["date_of_birth"])

    conflicting = dates.nunique().loc[lambda n: n > 1].index.difference(verified.index)
    if len(conflicting):
        raise ValueError(
            f"Conflicting date_of_birth across player_core files for athlete_id(s) "
            f"{list(conflicting)}; verify and add to {DOB_OVERRIDES_PATH.name}"
        )
    return verified.combine_first(dates.first())


def add_age(df, birth_dates, box):
    """Add age in decimal years on the season's first regular-season game date."""
    opening_day = pd.to_datetime(box["game_date"]).groupby(box["season"]).min()
    # reindex (not map) so the column stays datetime-typed when a birth date is missing.
    born = birth_dates.reindex(df["athlete_id"]).set_axis(df.index)
    df = df.copy()
    df["age_at_season_start"] = (df["season"].map(opening_day) - born).dt.days / 365.25
    return df


def validate(df, box):
    """Stop the build if the output breaks an invariant the decisions rely on."""
    if df.duplicated(["season", "athlete_id"]).any():
        raise ValueError("Expected one row per player-season; found duplicates")

    counting = ["games_played", "minutes"] + COMPONENTS
    if df[counting].isna().any().any():
        raise ValueError("Null in a counting column")

    # Every real team plays many games; a one-game team is an All-Star roster
    # that got past the name and schedule-note filters.
    games_per_team = box.groupby(["season", "team_display_name"])["game_id"].nunique()
    one_game_teams = games_per_team[games_per_team < 2]
    if len(one_game_teams):
        raise ValueError(f"Teams with a single game (All-Star leak?): {list(one_game_teams.index)}")

    over = df[df["team_minutes_share"] > MAX_TEAM_MINUTES_SHARE + SHARE_ROUNDING_TOLERANCE]
    if len(over):
        raise ValueError(
            f"team_minutes_share above {MAX_TEAM_MINUTES_SHARE}: "
            f"{over[['season', 'player_name', 'team_minutes_share']].to_dict('records')}"
        )

    no_age = df[df["age_at_season_start"].isna() & (df["minutes"] >= AGE_REQUIRED_MINUTES)]
    if len(no_age):
        raise ValueError(
            f"Missing age for player-seasons with {AGE_REQUIRED_MINUTES}+ minutes; look up "
            f"and add to {DOB_OVERRIDES_PATH.name}: {no_age[['season', 'player_name']].to_dict('records')}"
        )


def build_player_seasons(box, schedules, core, dob_overrides):
    """Raw frames in, validated player-season table out."""
    regular = filter_regular_season(box, excluded_game_ids(box, schedules))
    df = aggregate_player_seasons(regular)
    df = add_rates(df)
    df = add_team_shares(df, regular)
    df = add_age(df, resolve_birth_dates(core, dob_overrides), regular)
    validate(df, regular)
    return df


def main():
    download_raw()
    df = build_player_seasons(
        box=load_dataset("player_box"),
        schedules=load_dataset("wnba_schedule"),
        core=load_dataset("player_core"),
        dob_overrides=pd.read_csv(DOB_OVERRIDES_PATH),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)

    print(f"Wrote {len(df)} player-seasons to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(df.groupby("season").size().rename("player_seasons").to_string())


if __name__ == "__main__":
    main()
