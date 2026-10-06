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

**Reason for the reversal:** the round-2 finding that `player_season_stats` holds career totals, not season totals, for most veteran players (62% of 2025's 170 players show a physically-impossible single-season `gamesPlayed`) means it can't serve as a reliable cross-check — for most players, "cross-checking" against it would mean comparing our correct single-season numbers against its career numbers, which would look like our pipeline is wrong when it isn't.

**Replacement:** once the pipeline exists, spot-check its output against official season totals (WNBA.com or Basketball-Reference) for 5–10 players, covering a mix of roles/teams/minutes levels, as a pipeline acceptance step before trusting the output — the same method just used to verify the Commissioner's Cup exclusion above (Napheesa Collier's 2025 line matched exactly once the Championship and All-Star games were excluded). This becomes a required acceptance check for the pipeline build milestone, not an optional nicety.

**Alternative considered:** keep using `player_season_stats` as a cross-check but only for players/seasons where its `gamesPlayed` looks plausible for a single season. Rejected — a "plausible-looking" career total (e.g. a rookie or a player returning from injury, where a low career game count coincidentally looks like a season total) is indistinguishable from a real season total without already knowing the answer, so this wouldn't actually be a reliable filter.

The entries below were approved by Chloe on 2026-10-06, before the Milestone 1 pipeline build (`feat/pipeline-player-seasons`). They came out of checking the 2015–2026 `player_box`, `schedules`, and `player_core` parquet files against the filters approved above.

## 2026-10-06 — All-Star exclusion widened: name pattern OR `EAST`/`WEST` OR schedule note

**Status:** Approved (Chloe, 2026-10-06). **Extends** the 2026-10-01 All-Star decision above, which was only checked against 2025–2026.

The `^TEAM ` pattern misses two All-Star Games in the 2015–2026 range: in 2015 (`game_id 400765572`) and 2017 (`400968106`) the rosters are named `EAST` and `WEST`. The schedule's All-Star note can't replace the name pattern either — it is missing for the 2023 game (`401558893`, `Team Stewart`/`Team Wilson`). No single signal covers all ten All-Star Games (there was none in 2016 or 2020).

**How:** exclude a game if any of these is true: a team's `team_display_name` matches `^TEAM ` case-insensitively (2018–2024 use mixed case, e.g. `Team Delle Donne`); a team is named `EAST` or `WEST`; or `schedules.notes_headline` contains "All-Star" (case-insensitive). The exclusion is by `game_id`, so both rosters go together.

**Safety net:** the pipeline fails if, after filtering, any team has only one regular-season game in a season. That structural check on its own catches all ten All-Star Games, so a future naming change can't slip through silently.

**Alternative considered:** use the one-game-team rule as the filter itself. Rejected as the primary rule because it says nothing about *why* a game is excluded; kept as the check that the named rules worked.

## 2026-10-06 — 2021 Commissioner's Cup final excluded by explicit `game_id` override

**Status:** Approved (Chloe, 2026-10-06). **Extends** the 2026-10-01 Commissioner's Cup decision above.

The 2022–2026 finals carry `notes_headline == "WNBA Commissioner's Cup Championship"`. The inaugural 2021 final does not: `game_id 401353913` (Seattle Storm vs. Connecticut Sun, 2021-08-12, `neutral_site == True`) carries the plain group-play note `"WNBA Commissioner's Cup"`. Evidence that it is the extra game: Seattle and Connecticut each show 33 `season_type == 2` games in 2021 while the other ten teams show 32, the same finalists-plus-one pattern as later seasons, and the schedule lists 61 Cup-noted games (60 group games + this one).

**How:** headline match for the Championship, plus a hardcoded override for `401353913` with this entry as its justification.

**Alternative considered:** infer it from `neutral_site == True` plus the Cup note. Rejected — an inference from one example is no safer than naming the one game, and it is less obvious to a reader.

## 2026-10-06 — A game counts as played when `did_not_play` is false and `minutes` is not null

**Status:** Approved (Chloe, 2026-10-06).

Across 2015–2026 regular-season rows: 157 appearances have `minutes == 0` because ESPN rounds minutes to whole numbers, and some carry real stats (up to 2 points) — these count as games played, matching how official game counts treat a brief appearance. 85 rows are not marked `did_not_play` but have null `minutes`, `active == False`, and no nonzero stat — these are inactive-roster rows and do not count.

**Alternative considered:** require `minutes > 0`. Rejected — it would drop real appearances and undercount games against official totals.

## 2026-10-06 — Team shares for traded players use an on-roster window

**Status:** Approved (Chloe, 2026-10-06). Applies to both share of team minutes and share of games played.

- **One team all season:** denominator is that team's full regular season (all its games; team minutes = sum of all its players' minutes), as in the data audit.
- **More than one team (145 player-seasons, 10 with three or more):** the season is split into stints, a stint being a run of consecutive box-score rows with the same team in date order. Each stint's denominator covers only that team's games from her first to her last box row of the stint, did-not-play and inactive rows included, since they show she was on the roster. Stint denominators are summed.

Share of team minutes = player minutes ÷ team player-minutes in the window, so a player on the floor for every minute scores 0.2. The pipeline fails if any player-season exceeds 0.2 beyond a small rounding tolerance (minutes are whole numbers per game).

**Known limits:** a single-team player signed late or waived early is still measured against the full season; a traded player's window can't see games before her first box row with a new team.

**Alternative considered:** each team's full-season minutes for every player. Simpler, but it understates every traded player's share.

## 2026-10-06 — Age is decimal years on the season's first regular-season game date

**Status:** Approved (Chloe, 2026-10-06). Closes open item 9 in `docs/data-audit.md`.

Age = (date of the season's first regular-season game − `player_core.date_of_birth`) ÷ 365.25 days. `player_core.age` is not used (frozen at file build time).

**Conflicting birth dates** — three players have two different `date_of_birth` values across `player_core` season files. Each was verified on Basketball-Reference on 2026-10-06 and the verified value is recorded with its source in `pipeline/dob_overrides.csv`:

| Player (`athlete_id`) | `player_core` values | Verified | Source |
|---|---|---|---|
| Myisha Hines-Allen (3142055) | 1996-05-30 (2018–2025 files), 1995-05-30 (2026) | 1995-05-30 | https://www.basketball-reference.com/wnba/players/h/hinesmy01w.html |
| Maddy Westbeld (4433424) | 2002-10-15 (2025), 2002-02-10 (2026) | 2002-02-10 | https://www.basketball-reference.com/wnba/players/w/westbma01w.html |
| Aziaha James (4433807) | 2005-02-22 (2025), 2002-11-19 (2026) | 2002-11-19 | https://www.basketball-reference.com/wnba/players/j/jamesaz01w.html |

All three verified values happen to match the 2026 file, but the pipeline does not rely on "most recent file wins": a conflict with no override stops the build.

**Missing birth dates** — four player-seasons have no `date_of_birth` in any season's file. Per Chloe, look up only those at or above 200 minutes; all four are below it, so age stays null: Makayla Epps 2017 (64 min), Aleah Goodman 2021 (3), Raina Perez 2022 (2), Li Yueru 2022 (80). The pipeline fails if a player-season with 200+ minutes ever has a null age.

**Alternative considered:** take the most recent `player_core` file's value for conflicts. Rejected by Chloe — verify against an outside source and record it.

## 2026-10-06 — Pipeline output is parquet; JSON for the web app is a later export step

**Status:** Approved (Chloe, 2026-10-06).

`pipeline/build.py` writes `data/clean/player_seasons.parquet` (typed columns, list-valued `teams`). A later step will export JSON for the Next.js app. CLAUDE.md updated to match.

**Alternative considered:** write JSON directly, as CLAUDE.md originally said. Rejected — parquet keeps types for analysis; the app's JSON shape should be decided when the app exists.

## 2026-10-06 — Known data gaps carried into the pipeline (no decision needed)

- **One 2016 game is missing from `player_box`:** Seattle Storm vs. Connecticut Sun, 2016-05-28 (`game_id 400864463`, `STATUS_FINAL` in the schedule). Players on those two rosters will be one game short of official 2016 totals. No fix without a second source.
- **Minutes are whole numbers per game.** Season minutes can differ from Basketball-Reference by a few minutes, so the acceptance spot-check allows a small tolerance on minutes and Game Score per 40; counting stats must match exactly.
