"""Tiny hand-built frames shaped like the upstream parquet files."""

import pandas as pd

STAT_DEFAULTS = {
    "minutes": 20.0,
    "points": 0.0,
    "field_goals_made": 0.0,
    "field_goals_attempted": 0.0,
    "free_throws_made": 0.0,
    "free_throws_attempted": 0.0,
    "offensive_rebounds": 0.0,
    "defensive_rebounds": 0.0,
    "assists": 0.0,
    "steals": 0.0,
    "blocks": 0.0,
    "turnovers": 0.0,
    "fouls": 0.0,
}


def box_row(game_id, athlete_id, team, date="2025-06-01", **overrides):
    """One player_box row. `team` is the display name; team_id is derived from it."""
    row = {
        "game_id": game_id,
        "season": int(date[:4]),
        "season_type": 2,
        "game_date": date,
        "athlete_id": athlete_id,
        "athlete_display_name": f"Player {athlete_id}",
        "team_id": abs(hash(team)) % 100000,
        "team_display_name": team,
        "did_not_play": False,
        **STAT_DEFAULTS,
    }
    row.update(overrides)
    return row


def dnp_row(game_id, athlete_id, team, date="2025-06-01"):
    """A did-not-play row: upstream leaves every stat null."""
    nulls = {k: None for k in STAT_DEFAULTS}
    return box_row(game_id, athlete_id, team, date, did_not_play=True, **nulls)


def box(*rows):
    return pd.DataFrame(list(rows))


def schedule(*rows):
    """rows: (game_id, notes_headline)"""
    return pd.DataFrame(
        [{"game_id": g, "season_type": 2, "notes_headline": n} for g, n in rows]
    )
