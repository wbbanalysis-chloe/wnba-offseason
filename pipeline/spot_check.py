"""Acceptance check: compare pipeline output to official season lines.

Required by docs/decisions.md (2026-10-01 reversal: official-source spot-check
replaces player_season_stats as the cross-check). spot_check_reference.csv holds
two kinds of line for the same players, each with its source URL:

- wnba_com: season totals summed from the league's own game logs
  (stats.wnba.com, via sportsdataverse wnba_stats_player_game_logs).
- basketball_reference: regular-season totals read off the player's page.

Run after the build: python -m pipeline.spot_check
"""

import sys
from pathlib import Path

import pandas as pd

from pipeline import build

REFERENCE_PATH = Path(__file__).resolve().parent / "spot_check_reference.csv"

# Basketball-Reference column -> pipeline column. Counting stats must match exactly.
EXACT = {
    "g": "games_played",
    "pts": "points",
    "fg": "field_goals_made",
    "fga": "field_goals_attempted",
    "ft": "free_throws_made",
    "fta": "free_throws_attempted",
    "orb": "offensive_rebounds",
    "ast": "assists",
    "stl": "steals",
    "blk": "blocks",
    "tov": "turnovers",
    "pf": "fouls",
}

# Only a mismatch against this source fails the check. Basketball-Reference
# disagrees with the league's game logs by a stat or two in some older seasons
# (docs/decisions.md 2026-10-06), so its mismatches are printed, not fatal.
BLOCKING_SOURCE = "wnba_com"

# ESPN minutes are whole numbers per game, so season minutes (and anything
# divided by them) can drift slightly from the official total.
RELATIVE_TOLERANCE = {"minutes": 0.01, "game_score_per40": 0.01}


def official_lines(reference):
    """Reference rows renamed to pipeline columns, with the same derived rates."""
    official = reference.rename(columns={**EXACT, "mp": "minutes"})
    # Basketball-Reference lists total rebounds; the pipeline keeps the two halves.
    official["defensive_rebounds"] = reference["trb"] - reference["orb"]
    return build.add_rates(official)


def compare(output, reference):
    """One row per (player-season, stat): pipeline value, official value, pass/fail."""
    stats = list(EXACT.values()) + ["defensive_rebounds", "ts_pct"] + list(RELATIVE_TOLERANCE)
    key = ["player_name", "season"]  # reference may hold one line per source for each
    merged = official_lines(reference).merge(
        output, on=key, how="left", suffixes=("_official", "_pipeline")
    )
    rows = []
    for _, line in merged.iterrows():
        for stat in stats:
            ours, theirs = line[f"{stat}_pipeline"], line[f"{stat}_official"]
            allowed = RELATIVE_TOLERANCE.get(stat, 1e-9) * abs(theirs)
            rows.append({
                "player_name": line["player_name"],
                "season": line["season"],
                "source": line["source"],
                "stat": stat,
                "pipeline": ours,
                "official": theirs,
                # A player missing from the output gives NaN here, which is not <=.
                "ok": abs(ours - theirs) <= allowed,
            })
    return pd.DataFrame(rows)


def blocking_failures(result):
    """Mismatches that fail acceptance: those against the league's own numbers."""
    return result[~result["ok"] & (result["source"] == BLOCKING_SOURCE)]


def main():
    result = compare(pd.read_parquet(build.OUTPUT_PATH), pd.read_csv(REFERENCE_PATH))
    summary = result.groupby(["source", "player_name", "season"], sort=False)["ok"].agg(
        passed="sum", checked="size"
    )
    print(summary.to_string())

    known = result[~result["ok"] & (result["source"] != BLOCKING_SOURCE)]
    if len(known):
        print("\nDiffers from Basketball-Reference (reported, not fatal):")
        print(known.to_string(index=False))

    failed = blocking_failures(result)
    if len(failed):
        print(f"\nMISMATCH against {BLOCKING_SOURCE}:\n" + failed.to_string(index=False))
        sys.exit(1)
    checked = (result["source"] == BLOCKING_SOURCE).sum()
    print(f"\nAll {checked} comparisons against {BLOCKING_SOURCE} passed.")


if __name__ == "__main__":
    main()
