import pandas as pd
import pytest

from pipeline import build
from tests.helpers import box, box_row


def core(*rows):
    """rows: (season, athlete_id, date_of_birth) in upstream's string format."""
    return pd.DataFrame(rows, columns=["season", "athlete_id", "date_of_birth"])


NO_OVERRIDES = pd.DataFrame(columns=["athlete_id", "date_of_birth"])


def test_same_birth_date_in_every_season_file_resolves_to_that_date():
    c = core((2024, 10, "1996-09-23T07:00Z"), (2025, 10, "1996-09-23T07:00Z"))

    assert build.resolve_birth_dates(c, NO_OVERRIDES)[10] == pd.Timestamp("1996-09-23")


def test_conflicting_birth_dates_without_a_verified_override_stop_the_build():
    c = core((2025, 10, "1996-05-30T07:00Z"), (2026, 10, "1995-05-30T07:00Z"))

    with pytest.raises(ValueError, match="10"):
        build.resolve_birth_dates(c, NO_OVERRIDES)


def test_verified_override_wins_over_conflicting_files():
    c = core((2025, 10, "1996-05-30T07:00Z"), (2026, 10, "1995-05-30T07:00Z"))
    overrides = pd.DataFrame({"athlete_id": [10], "date_of_birth": ["1995-05-30"]})

    assert build.resolve_birth_dates(c, overrides)[10] == pd.Timestamp("1995-05-30")


def test_age_is_decimal_years_on_the_seasons_first_game_not_the_players():
    b = box(
        box_row(1, 11, "Lynx", "2025-05-16"),  # season opener, someone else
        box_row(2, 10, "Lynx", "2025-07-01"),  # her first game, weeks later
    )
    births = pd.Series({10: pd.Timestamp("1996-05-16"), 11: pd.Timestamp("2000-01-01")})

    out = build.add_age(build.aggregate_player_seasons(b), births, b)

    age = out.set_index("athlete_id")["age_at_season_start"]
    assert age[10] == pytest.approx(29.0, abs=0.01)


def test_player_with_no_birth_date_gets_null_age():
    b = box(box_row(1, 10, "Lynx", "2025-05-16"))

    out = build.add_age(build.aggregate_player_seasons(b), pd.Series(dtype="datetime64[ns]"), b)

    assert pd.isna(out.iloc[0]["age_at_season_start"])
