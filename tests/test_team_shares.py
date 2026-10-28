import pytest

from pipeline import build
from tests.helpers import box, box_row, dnp_row

# Sun play games 1-3, Tempo play games 4-6, on alternating dates.
SUN_DATES = {1: "2025-06-01", 2: "2025-06-03", 3: "2025-06-05"}
TEMPO_DATES = {4: "2025-06-02", 5: "2025-06-04", 6: "2025-06-06"}


def regulars():
    """One 30-minute regular per team in every game, so team totals are easy to add up."""
    sun = [box_row(g, 11, "Sun", d, minutes=30.0) for g, d in SUN_DATES.items()]
    tempo = [box_row(g, 13, "Tempo", d, minutes=30.0) for g, d in TEMPO_DATES.items()]
    return sun + tempo


def shares_for(athlete_id, *extra_rows):
    b = box(*regulars(), *extra_rows)
    out = build.add_team_shares(build.aggregate_player_seasons(b), b)
    row = out[out["athlete_id"] == athlete_id].iloc[0]
    return row["team_minutes_share"], row["team_games_share"]


def test_single_team_player_is_measured_against_the_full_team_season():
    # Plays games 1-2 and has no row at all for game 3; game 3 still counts against her.
    minutes_share, games_share = shares_for(
        10,
        box_row(1, 10, "Sun", SUN_DATES[1], minutes=20.0),
        box_row(2, 10, "Sun", SUN_DATES[2], minutes=20.0),
    )

    assert minutes_share == pytest.approx(40 / (3 * 30 + 40))
    assert games_share == pytest.approx(2 / 3)


def test_traded_player_is_measured_only_against_games_while_on_each_roster():
    # Sun for game 1, then Tempo for games 5-6. Sun games 2-3 and Tempo game 4 are outside her windows.
    minutes_share, games_share = shares_for(
        12,
        box_row(1, 12, "Sun", SUN_DATES[1], minutes=10.0),
        box_row(5, 12, "Tempo", TEMPO_DATES[5], minutes=20.0),
        box_row(6, 12, "Tempo", TEMPO_DATES[6], minutes=20.0),
    )

    assert minutes_share == pytest.approx(50 / ((30 + 10) + 2 * (30 + 20)))
    assert games_share == pytest.approx(3 / 3)


def test_did_not_play_row_extends_the_roster_window():
    # On the Tempo bench for game 4, so game 4 is inside her window even though she sat.
    minutes_share, games_share = shares_for(
        12,
        box_row(1, 12, "Sun", SUN_DATES[1], minutes=10.0),
        dnp_row(4, 12, "Tempo", TEMPO_DATES[4]),
        box_row(5, 12, "Tempo", TEMPO_DATES[5], minutes=20.0),
    )

    assert minutes_share == pytest.approx(30 / ((30 + 10) + (30 + 30 + 20)))
    assert games_share == pytest.approx(2 / 3)


def test_returning_to_a_former_team_does_not_count_the_games_in_between():
    # Sun game 1, Tempo game 4, back to Sun for game 3. Sun game 2 fell while she was a Tempo player.
    minutes_share, games_share = shares_for(
        12,
        box_row(1, 12, "Sun", SUN_DATES[1], minutes=10.0),
        box_row(4, 12, "Tempo", TEMPO_DATES[4], minutes=10.0),
        box_row(3, 12, "Sun", SUN_DATES[3], minutes=10.0),
    )

    assert minutes_share == pytest.approx(30 / (3 * (30 + 10)))
    assert games_share == pytest.approx(3 / 3)
