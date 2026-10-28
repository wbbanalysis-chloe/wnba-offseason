import pandas as pd

from pipeline import build, spot_check

REFERENCE = {
    "player_name": "Player 10", "season": 2025, "source": "wnba_com", "g": 2, "mp": 60, "fg": 8, "fga": 15, "ft": 3,
    "fta": 5, "orb": 2, "trb": 8, "ast": 4, "stl": 3, "blk": 1, "tov": 3, "pf": 2, "pts": 20,
}


def pipeline_row(**changes):
    row = {
        "player_name": "Player 10", "season": 2025, "games_played": 2, "minutes": 60.0,
        "field_goals_made": 8.0, "field_goals_attempted": 15.0, "free_throws_made": 3.0,
        "free_throws_attempted": 5.0, "offensive_rebounds": 2.0, "defensive_rebounds": 6.0,
        "assists": 4.0, "steals": 3.0, "blocks": 1.0, "turnovers": 3.0, "fouls": 2.0, "points": 20.0,
    }
    row.update(changes)
    return build.add_rates(pd.DataFrame([row]))


def failures(**changes):
    result = spot_check.compare(pipeline_row(**changes), pd.DataFrame([REFERENCE]))
    return list(result.loc[~result["ok"], "stat"])


def test_identical_line_passes_every_stat():
    assert failures() == []


def test_counting_stat_off_by_one_fails():
    assert "points" in failures(points=21.0)


def test_defensive_rebounds_checked_as_total_minus_offensive():
    assert "defensive_rebounds" in failures(defensive_rebounds=7.0)


def test_minutes_within_rounding_tolerance_pass():
    # 60.5 vs 60: under 1%. Game Score per 40 moves with it but stays inside its tolerance.
    assert failures(minutes=60.5) == []


def test_minutes_beyond_rounding_tolerance_fail():
    assert "minutes" in failures(minutes=63.0)


def test_player_missing_from_pipeline_output_fails():
    result = spot_check.compare(pipeline_row(player_name="Someone Else"), pd.DataFrame([REFERENCE]))

    assert not result["ok"].any()


def test_only_wnba_com_mismatches_block_acceptance():
    # Basketball-Reference differs from the official log by a stat or two in older
    # seasons (docs/decisions.md), so its mismatches are reported, not fatal.
    reference = pd.DataFrame([REFERENCE, {**REFERENCE, "source": "basketball_reference"}])
    result = spot_check.compare(pipeline_row(assists=5.0), reference)

    blocking = spot_check.blocking_failures(result)

    assert set(blocking["source"]) == {"wnba_com"}
    assert "assists" in set(blocking["stat"])
