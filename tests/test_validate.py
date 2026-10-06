import pandas as pd
import pytest

from pipeline import build
from tests.helpers import box, box_row


# Per-game minutes for one team: four players on the floor all game, two splitting a spot.
MINUTES = {10: 30.0, 11: 40.0, 12: 40.0, 13: 40.0, 14: 40.0, 15: 10.0}


def clean_box():
    """Six Lynx games: players 11-14 reach 240 minutes, player 10 only 180."""
    return box(*[
        box_row(game, athlete, "Lynx", f"2025-06-{game:02d}", minutes=minutes)
        for game in range(1, 7)
        for athlete, minutes in MINUTES.items()
    ])


def built(b):
    births = pd.Series({a: pd.Timestamp("1996-09-23") for a in MINUTES})
    df = build.add_rates(build.aggregate_player_seasons(b))
    return build.add_age(build.add_team_shares(df, b), births, b)


def test_clean_output_passes():
    b = clean_box()

    build.validate(built(b), b)


def test_duplicate_player_season_fails():
    b = clean_box()
    df = built(b)

    with pytest.raises(ValueError, match="one row per player-season"):
        build.validate(pd.concat([df, df.iloc[[0]]]), b)


def test_team_with_a_single_game_fails_as_a_leaked_all_star_roster():
    b = pd.concat([clean_box(), box(box_row(3, 10, "Stars", "2025-07-19"))])

    with pytest.raises(ValueError, match="Stars"):
        build.validate(built(b), b)


def test_team_minutes_share_above_one_fifth_fails():
    b = clean_box()
    df = built(b)
    df.loc[0, "team_minutes_share"] = 0.25

    with pytest.raises(ValueError, match="team_minutes_share"):
        build.validate(df, b)


def test_rotation_player_without_an_age_fails():
    b = clean_box()
    df = built(b)
    df.loc[df["athlete_id"] == 11, "age_at_season_start"] = None  # 240 minutes

    with pytest.raises(ValueError, match="age"):
        build.validate(df, b)


def test_low_minutes_player_without_an_age_is_allowed():
    b = clean_box()
    df = built(b)
    df.loc[df["athlete_id"] == 10, "age_at_season_start"] = None  # 180 minutes

    build.validate(df, b)
