import pandas as pd
import pytest

from pipeline import build
from tests.helpers import box, box_row, dnp_row


def only_row(df):
    assert len(df) == 1
    return df.iloc[0]


def test_one_row_per_player_season():
    b = box(
        box_row(1, 10, "Lynx", "2024-06-01"),
        box_row(2, 10, "Lynx", "2025-06-01"),
        box_row(3, 10, "Lynx", "2025-06-03"),
        box_row(3, 11, "Lynx", "2025-06-03"),
    )

    out = build.aggregate_player_seasons(b)

    assert sorted(zip(out["season"], out["athlete_id"])) == [(2024, 10), (2025, 10), (2025, 11)]


def test_sums_minutes_and_components_over_played_games():
    b = box(
        box_row(1, 10, "Lynx", minutes=30.0, points=20.0, assists=4.0),
        box_row(2, 10, "Lynx", "2025-06-03", minutes=25.0, points=11.0, assists=1.0),
    )

    row = only_row(build.aggregate_player_seasons(b))

    assert (row["games_played"], row["minutes"], row["points"], row["assists"]) == (2, 55.0, 31.0, 5.0)


def test_did_not_play_rows_do_not_count_as_games():
    b = box(box_row(1, 10, "Lynx"), dnp_row(2, 10, "Lynx", "2025-06-03"))

    assert only_row(build.aggregate_player_seasons(b))["games_played"] == 1


def test_zero_minute_appearance_counts_as_a_game():
    b = box(box_row(1, 10, "Lynx", minutes=0.0, points=2.0))

    row = only_row(build.aggregate_player_seasons(b))

    assert (row["games_played"], row["points"]) == (1, 2.0)


def test_inactive_row_with_null_minutes_does_not_count_as_a_game():
    b = box(box_row(1, 10, "Lynx"), box_row(2, 10, "Lynx", "2025-06-03", minutes=None))

    assert only_row(build.aggregate_player_seasons(b))["games_played"] == 1


def test_player_who_never_played_has_no_row():
    b = box(box_row(1, 10, "Lynx"), dnp_row(1, 11, "Lynx"))

    assert list(build.aggregate_player_seasons(b)["athlete_id"]) == [10]


def test_teams_listed_in_order_of_first_appearance():
    b = box(
        box_row(3, 10, "Tempo", "2025-08-02"),
        box_row(1, 10, "Sun", "2025-06-01"),
        box_row(2, 10, "Sun", "2025-06-03"),
    )

    row = only_row(build.aggregate_player_seasons(b))

    assert (list(row["teams"]), row["n_teams"]) == (["Sun", "Tempo"], 2)


def test_game_score_uses_hollinger_weights():
    # 20 + 0.4*8 - 0.7*15 - 0.4*(5-3) + 0.7*2 + 0.3*6 + 3 + 0.7*4 + 0.7*1 - 0.4*2 - 3 = 17.8
    totals = pd.DataFrame([{
        "minutes": 30.0, "points": 20.0, "field_goals_made": 8.0, "field_goals_attempted": 15.0,
        "free_throws_made": 3.0, "free_throws_attempted": 5.0, "offensive_rebounds": 2.0,
        "defensive_rebounds": 6.0, "steals": 3.0, "assists": 4.0, "blocks": 1.0,
        "fouls": 2.0, "turnovers": 3.0,
    }])

    row = only_row(build.add_rates(totals))

    assert row["game_score"] == pytest.approx(17.8)
    assert row["game_score_per40"] == pytest.approx(17.8 / 30 * 40)


def test_true_shooting_percentage():
    totals = pd.DataFrame([{**{c: 0.0 for c in build.COMPONENTS}, "minutes": 30.0,
                            "points": 20.0, "field_goals_attempted": 15.0, "free_throws_attempted": 5.0}])

    assert only_row(build.add_rates(totals))["ts_pct"] == pytest.approx(20 / (2 * (15 + 0.44 * 5)))


def test_rates_are_null_not_infinite_when_denominator_is_zero():
    totals = pd.DataFrame([{**{c: 0.0 for c in build.COMPONENTS}, "minutes": 0.0, "points": 0.0}])

    row = only_row(build.add_rates(totals))

    assert pd.isna(row["game_score_per40"]) and pd.isna(row["ts_pct"])
