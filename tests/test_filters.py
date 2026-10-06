import pandas as pd

from pipeline import build
from tests.helpers import box, box_row, schedule


def test_load_dataset_concatenates_every_season_file(tmp_path):
    for season in (2015, 2016):
        pd.DataFrame({"season": [season]}).to_parquet(tmp_path / f"player_box_{season}.parquet")

    loaded = build.load_dataset("player_box", [2015, 2016], raw_dir=tmp_path)

    assert sorted(loaded["season"]) == [2015, 2016]


def test_excludes_game_with_team_prefixed_rosters_in_any_case():
    b = box(
        box_row(1, 10, "Minnesota Lynx"),
        box_row(2, 10, "TEAM COLLIER"),
        box_row(3, 10, "Team Delle Donne"),
    )

    assert build.excluded_game_ids(b, schedule((1, ""), (2, ""), (3, ""))) == {2, 3}


def test_excludes_east_west_all_star_rosters():
    b = box(box_row(1, 10, "EAST"), box_row(1, 11, "WEST"), box_row(2, 10, "Seattle Storm"))

    assert build.excluded_game_ids(b, schedule((1, ""), (2, ""))) == {1}


def test_excludes_game_flagged_all_star_in_schedule_even_with_real_looking_names():
    b = box(box_row(1, 10, "Stars"), box_row(2, 10, "Seattle Storm"))

    excluded = build.excluded_game_ids(b, schedule((1, "AT&T WNBA All-Star Game"), (2, "")))

    assert excluded == {1}


def test_excludes_cup_championship_but_keeps_cup_group_games():
    b = box(box_row(1, 10, "Minnesota Lynx"), box_row(2, 10, "Minnesota Lynx"))
    s = schedule((1, "WNBA Commissioner's Cup"), (2, "WNBA Commissioner's Cup Championship"))

    assert build.excluded_game_ids(b, s) == {2}


def test_excludes_unlabelled_2021_cup_final_by_game_id():
    b = box(box_row(401353913, 10, "Seattle Storm", date="2021-08-12"))
    s = schedule((401353913, "WNBA Commissioner's Cup"))

    assert build.excluded_game_ids(b, s) == {401353913}


def test_filter_keeps_only_regular_season_rows_outside_excluded_games():
    b = box(
        box_row(1, 10, "Minnesota Lynx"),
        box_row(2, 10, "Minnesota Lynx", season_type=3),
        box_row(3, 10, "TEAM COLLIER"),
    )

    kept = build.filter_regular_season(b, excluded={3})

    assert list(kept["game_id"]) == [1]
