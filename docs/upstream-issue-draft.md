<!--
Draft GitHub issue for sportsdataverse/wehoop-wnba-data.
Not posted — for Chloe to review and post herself from her own account.
Source: docs/data-audit.md §8, found 2026-10-01 while auditing the data for the WNBA Offseason Impact project.
-->

# `player_season_stats` appears to hold career totals, not season totals, for most veteran players

## Summary

In the `player_season_stats` release (file stem `player_season_stats_{season}.{csv,parquet,rds}`), the `totals` and `averages` rows for a given `(season, athlete_id)` appear to be **career-cumulative** for most players who have more than one WNBA season under their belt, rather than totals for just that `season`. The file is named and keyed by a single season (e.g. `player_season_stats_2025.csv`, `season == 2025`), so this is surprising — the per-season rows should presumably reflect that season only.

## Example

Player: **Napheesa Collier** (`athlete_id` 3917450), `player_season_stats_2025.csv`, `season == 2025`.

| Stat | Value in `player_season_stats_2025.csv` | Expected (2025 regular season only) | Source for expected value |
|---|---:|---:|---|
| `gamesPlayed` (category `averages`) | **193** | **33** | [Basketball-Reference](https://www.basketball-reference.com/wnba/players/c/collina01w.html), [ESPN stats](https://www.espn.com/wnba/player/stats/_/id/3917450/napheesa-collier) |
| `totals.points` (category `totals`) | **3542** | **755** | same |
| `avgPoints` (category `averages`) | 18.4 | 22.9 | same |

193 games is not possible in a single WNBA season (the 2025 regular season was 44 games/team). Collier entered the WNBA in 2019, so 193 looks like a career total through the 2025 season — and `avgPoints (18.4) × gamesPlayed (193) ≈ totals.points (3542)`, so the row is internally consistent, just consistently a **career** total rather than a **2025 season** total.

We independently verified the expected 2025-only values directly from `player_box` (the game-by-game box score dataset), by taking Collier's full 2025 `season_type == 2` game log and removing the two rows that shouldn't count toward a regular-season total anyway (the Commissioner's Cup Championship Game and her All-Star Game appearance). The remaining 33 games sum to exactly 755 points (22.9 ppg), matching Basketball-Reference and ESPN's official stats page exactly — along with every other per-game stat we checked (rebounds, assists, minutes, steals, blocks). So `player_box` has the correct season-only data; it's specifically `player_season_stats` that appears to be returning career totals for this player.

## Scope / how widespread this is

Checked every player in `player_season_stats_2025.csv` for a `gamesPlayed` value that's physically impossible for a single WNBA season (i.e. > 45, generously allowing for the extra Commissioner's Cup Championship game):

- **170** players have a `gamesPlayed` row in that file.
- **105 of them (62%)** show `gamesPlayed` > 45 — e.g. DeWanna Bonner at 537, Nneka Ogwumike at 437, Courtney Vandersloot at 436.

This is very likely a lower bound on the share of affected players: a rookie or a player with only a handful of career games would show a `gamesPlayed` value that *looks* plausible for a single season even if it's actually a career total, so we can't distinguish those cases with this check alone — only the ones where the career count is already implausibly large for one season.

We haven't yet checked whether this also affects `player_season_stats` for earlier seasons (2002–2021, 2023–2024) or the in-progress 2026 file.

## Why this matters

Anyone using `player_season_stats` to compute or sanity-check single-season per-game rates for a player with WNBA tenure will get numbers far off from the official season stats, without any obvious signal that something's wrong (the `averages` and `totals` rows are internally consistent with each other — they just aren't consistent with the stated `season`).

## Suggested next step

Would appreciate a pointer to whether this is a known issue with the ESPN season-stats endpoint itself (e.g. it returning a "career" stats block under the same keys as the "season" block for some players) or something in the `wehoop-wnba-data` build step (`python/espn_wnba_05_player_season_stats_creation.py`) that isn't distinguishing between them. Happy to share the exact rows/queries used above if helpful.
