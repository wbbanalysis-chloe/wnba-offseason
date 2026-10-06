# Decisions

Assumptions and method choices that shape the findings, logged as they're made. Each entry: the decision, why, and the alternative considered. See `docs/data-audit.md` for the data audit these first four came out of.

The first four entries below were approved by Chloe in PR #1 review (2026-10-01).

## 2026-10-01 — Derive 2022 season totals from `player_box`, don't wait on upstream

**Status:** Approved (Chloe, PR #1 review, 2026-10-01).

`sportsdataverse/wehoop-wnba-data`'s `player_season_stats` dataset is missing the 2022 season entirely (every other season from 2002–2026 is present). Rather than blocking on an upstream backfill, the pipeline will derive 2022 player-season totals by aggregating `player_box` game logs for that year, which **is** complete.

**Alternative considered:** wait for/file an issue against upstream and hold off on 2022 until it's backfilled. Rejected because it blocks the pipeline on someone else's timeline for a gap we can fill ourselves from data we already have.

## 2026-10-01 — Build per-game and per-40 stats from `player_box`, not by pivoting `player_season_stats`

**Status:** Approved (Chloe, PR #1 review, 2026-10-01).

Per-40, not per-36 — a WNBA game is 40 minutes (4×10), not the NBA's 48; per-36 was a leftover and has been corrected throughout (CLAUDE.md included).

`player_season_stats` is long-format (one row per stat) and only exposes ESPN's pre-rounded `avgMinutes`/per-game averages, not raw total minutes. Multiplying `avgMinutes × gamesPlayed` would compound that rounding. The pipeline will instead sum `minutes`, `points`, etc. directly from `player_box` game logs per player-season, which is exact and uses the same source table end to end.

**Alternative considered:** pivot `player_season_stats`'s long format into per-player-season rows and use ESPN's own averages/totals directly. Rejected for precision (rounding compounds) and because it doesn't cover 2022 (see above) — `player_season_stats` will still be used as a cross-check against our own rollups, not as the primary source.

## 2026-10-01 — Read `.parquet`, not `.csv`, from wehoop-wnba-data releases

**Status:** Approved (Chloe, PR #1 review, 2026-10-01).

Boolean columns (`did_not_play`, `starter`, `ejected`, `active`) are serialized inconsistently across season CSVs — `TRUE`/`FALSE` (uppercase) in the 2025 file, `true`/`false` (lowercase) in the 2026 file. A naive string comparison reading CSVs will silently miss rows (this bit the audit script itself). Parquet stores these as typed booleans and avoids the casing trap.

**Alternative considered:** read CSV for simplicity (no parquet library dependency) and normalize boolean strings ourselves. Rejected — reading parquet removes the failure mode entirely instead of patching around it, and pandas reads parquet natively.

_Follow-up (2026-10-01, PR #1 review): spot-checked 2023 and 2024 too — both use uppercase `TRUE`/`FALSE` like 2025, so the lowercase `true`/`false` form is a 2026-only change. Doesn't change the decision; parquet sidesteps it regardless of which years it affects._

## 2026-10-01 — Match offseason assignments to WNBA players by name, with a logged confidence/method, not by ID

**Status:** Approved (Chloe, PR #1 review, 2026-10-01).

`data/raw/offseason_assignments.csv` doesn't exist yet, and when it's built (likely from a source like the WNBA Offseason Player Tracker blog post) it almost certainly won't carry ESPN `athlete_id`s. The only existing cross-source ID crosswalk in wehoop-wnba-data (`player_crosswalk`) covers 2026 only and doesn't know about Unrivaled, Athletes Unlimited, or overseas leagues at all. The join will be primarily name-based, using `player_core` (date of birth, college) to disambiguate players who share a name, and will carry its own `match_method`/`match_confidence` columns (mirroring `player_crosswalk`'s pattern) so weak or ambiguous matches are visible and reviewable rather than silently wrong.

**Alternative considered:** wait for or build a dedicated ID crosswalk that spans offseason leagues before doing any matching. Rejected — no such crosswalk exists today and building one is its own project; logging match confidence lets us ship the name-based join now while keeping bad matches auditable.

## 2026-10-01 — Exclude the WNBA All-Star Game from all analysis

**Status:** Approved (Chloe, PR #1 review round 2, 2026-10-01).

`player_box`/`team_box` tag the All-Star Game with `season_type == 2`, the same as real regular-season games, but under fictitious team rosters that aren't on any real team's schedule (`TEAM CLARK`/`TEAM COLLIER` in 2025, `TEAM SPOON`/`TEAM COOP` in 2026 — the exact names and `team_id`s change every year). Left in, it makes every All-Star look like they were traded to a team that doesn't exist, and inflates games-played/team-minutes denominators.

**How:** before computing any measure that groups by player + team (games-played share, team-minutes share, usage%'s team denominator, team-change detection), drop rows where `team_display_name` matches `^TEAM ` (case-insensitive). Don't hardcode specific `team_id`s — they're reassigned each season, so the name pattern is the stable signal, not the id.

**Alternative considered:** filter by `season_type` alone. Rejected — the All-Star Game carries `season_type == 2`, identical to real regular-season games, so `season_type` can't distinguish it; the team-name pattern is required.

## 2026-10-01 — Usage% denominator uses `team_box.total_turnovers`

**Status:** Approved (Chloe, PR #1 review round 2, 2026-10-01).

`team_box` has three turnover-shaped columns: `turnovers`, `team_turnovers`, and `total_turnovers`. Verified empirically against every 2025 team-game row (624 team-game rows, both season types):
- `team_box.turnovers` equals the sum of `player_box.turnovers` for that `(game_id, team_id)` in every single row (0 mismatches) — i.e. `turnovers` is individual-only.
- `team_box.total_turnovers` equals `team_box.turnovers + team_box.team_turnovers` in every single row (0 mismatches) — i.e. `total_turnovers` is individual + team-charged combined. `team_turnovers` (shot-clock violations, 8-second backcourt, etc., not credited to a player) is nonzero in 403 of the 624 rows checked, so the distinction is real, not a column that's always zero.

Usage% will use `team_box.total_turnovers` as the "team TOV" input, matching the Basketball-Reference usage-rate convention (team turnovers including team-charged turnovers).

**Alternative considered:** `team_box.turnovers` (individual-only). Rejected — it would understate the true team turnover denominator by excluding team-charged turnovers, which are real possessions lost.

## 2026-10-01 — Exclude the Commissioner's Cup Championship Game from all analysis

**Status:** Approved (Chloe, PR #1 review round 3, 2026-10-01).

Per the data audit (§7): the Championship Game is tagged `season_type == 2` like a real regular-season game, uses real teams/rosters (not a fake roster like the All-Star Game), and is a genuine extra 45th game for the season's two Commissioner's Cup finalists. Confirmed for both 2025 (Lynx/Fever) and 2026 (Liberty/Aces).

**Verified directly against official stats, per the review request**, using Napheesa Collier (2025 Lynx, a finalist) as the test case: her `player_box` game log has 35 `season_type == 2` rows marked as played — 33 real Lynx games, plus the Commissioner's Cup Championship (`game_id 401736430`, 12 points) and her 2025 All-Star Game appearance (`game_id 401781604`, under the fictitious `TEAM CLARK` roster, 36 points). Removing *both* of those two rows and summing the remaining 33 games gives an **exact** match to her official 2025 season line on both Basketball-Reference and ESPN's stats page: 33 games, 755 total points (22.9 ppg), 7.3 rpg, 3.2 apg, 32.3 mpg, 1.6 spg, 1.5 bpg — every single stat checked matched exactly. This confirms the Commissioner's Cup Championship Game's stats (like the All-Star Game's) **do not** count toward official WNBA regular-season totals, and independently reconfirms the All-Star exclusion decision above via a different method (direct comparison to an external source rather than internal game-count arithmetic).

**How:** identify the Championship Game by `game_id`, joined from the `schedules` dataset's `notes_headline == "WNBA Commissioner's Cup Championship"` field (there's no team-name pattern to filter on, unlike All-Star, since it uses real team rosters) — `game_id 401736430` for 2025, `401857321` for 2026, re-looked-up each new season. Exclude it before computing any per-game/per-40/games-played/team-minutes measure.

**Alternative considered:** include it, on the grounds that it's real production from a real competitive game. Rejected — the exact match to official totals when excluding it (and the mismatch when including it) settles that the official record treats it as non-regular-season, so including it would make our numbers diverge from the standard everyone else is using.

## 2026-10-01 — Reversal: drop `player_season_stats` as a cross-check

**Status:** Approved (Chloe, PR #1 review round 3, 2026-10-01). **Supersedes part of** the "Build per-game and per-40 stats from `player_box`" decision above, which had proposed keeping `player_season_stats` as a cross-check against our own rollups.

**Upstream issue:** reported as [sportsdataverse/wehoop-wnba-data#29](https://github.com/sportsdataverse/wehoop-wnba-data/issues/29) (open as of 2026-10-06).

**Reason for the reversal:** the round-2 finding that `player_season_stats` holds career totals, not season totals, for most veteran players (62% of 2025's 170 players show a physically-impossible single-season `gamesPlayed`) means it can't serve as a reliable cross-check — for most players, "cross-checking" against it would mean comparing our correct single-season numbers against its career numbers, which would look like our pipeline is wrong when it isn't.

**Replacement:** once the pipeline exists, spot-check its output against official season totals (WNBA.com or Basketball-Reference) for 5–10 players, covering a mix of roles/teams/minutes levels, as a pipeline acceptance step before trusting the output — the same method just used to verify the Commissioner's Cup exclusion above (Napheesa Collier's 2025 line matched exactly once the Championship and All-Star games were excluded). This becomes a required acceptance check for the pipeline build milestone, not an optional nicety.

**Alternative considered:** keep using `player_season_stats` as a cross-check but only for players/seasons where its `gamesPlayed` looks plausible for a single season. Rejected — a "plausible-looking" career total (e.g. a rookie or a player returning from injury, where a low career game count coincidentally looks like a season total) is indistinguishable from a real season total without already knowing the answer, so this wouldn't actually be a reliable filter.
