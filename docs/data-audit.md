# Data audit: sportsdataverse/wehoop-wnba-data

_First pass 2026-10-01. Updated 2026-10-01 after PR #1 review (per-40 correction, Game Score/usage/team-minutes/half-split feasibility, 2026 season completeness + World Cup data check, season_type/All-Star wrinkle, 2023–2024 spot-checks). Checked via the GitHub API/CLI against the `wehoop-wnba-data` repo (data dictionaries in `docs/datasets/*.md`) and the `sportsdataverse-data` releases that actually hold the files. Spot-checks ran against downloaded `player_box_{2023,2024,2025,2026}.csv`, `player_core_2025.csv`, and a sample of `player_season_stats_2025.csv` in a scratch directory — nothing was added to this repo. No pipeline code was written._

## TL;DR

- **2025 and 2026 are both present and current** in the per-game player box scores (`player_box`), refreshed as of today. 2026 regular-season game logs run **May 8 – Sep 24, 2026** with no games logged during the FIBA World Cup break (Aug 31 – Sep 16) — matches `docs/league-rules.md` exactly.
- **No FIBA Women's World Cup roster or box score data exists anywhere in sportsdataverse** (checked for a dedicated repo and for any international/FIBA build step in `wehoop-wnba-data`'s own scripts — there isn't one). WWC participation stays WNBA-external context, exactly as `league-rules.md` already treats it; nothing to pull in for performance numbers.
- **Season totals (`player_season_stats`) have a real gap: 2022 is missing entirely.** Confirmed, not hypothetical.
- Per-game box scores exist with a rich column set, including `did_not_play` and `reason`, and every component needed for Game Score (FGM, FGA, FTM, FTA, OREB, DREB, AST, STL, BLK, TOV, PF, PTS). Season totals are a separate, **long-format** table (one row per stat) with per-game averages and totals already computed by ESPN.
- **Minutes do include overtime.** Confirmed with a real 4-OT game (two WNBA teams, June 28, 2026) where summed player-minutes per team (300–302) matched 4 OT periods exactly.
- **`reason` is unreliable unless you filter on `did_not_play == true` first** — populated with `"COACH'S DECISION"` on ~84–85% of *played* rows too, consistently across all four seasons checked (2023, 2024, 2025, 2026). This is a durable characteristic of the source data, not a one-off glitch.
- **Boolean columns are serialized inconsistently across season CSVs**: `TRUE`/`FALSE` (2023, 2024, 2025) vs. `true`/`false` (2026 only). Parquet avoids this because booleans are typed — recommend reading parquet, not CSV, in the pipeline.
- **`season_type` separates regular season (2) from postseason (3) cleanly for game dates — but the All-Star Game is also tagged `season_type == 2`**, under fictitious team rosters (`TEAM CLARK` / `TEAM COLLIER` in 2025, `TEAM SPOON` / `TEAM COOP` in 2026) with their own `team_id`s. This will corrupt games-played counts, team-minute shares, and team-change detection if those All-Star rows aren't filtered out first — see §6 and the new open item below. This is new since the first pass; it surfaced while checking whether "share of team minutes" and "team change" are supported.
- **Players are identified by stable ESPN `athlete_id`s** that persist across seasons and don't collide within a season. Real in-season trades exist and are distinguishable from the All-Star artifact (confirmed with a concrete example, §6). There's a `player_crosswalk` dataset for cross-source ID matching, but it's **only built for 2026** and doesn't cover Unrivaled or Athletes Unlimited at all — matching our hand-built offseason CSV to `athlete_id` will be name-based, with `player_core` as a disambiguator.
- **The Commissioner's Cup Championship Game is excluded from analysis** (decided and verified in review round 3) — tagged `season_type == 2` like a real game, uses real rosters (unlike the fake All-Star teams), and is a genuine extra 45th game for the two finalists. Verified by an exact match to official stats once it (and the All-Star Game) are removed from a finalist's game log. See §7.
- **`player_season_stats` holds career totals, not season totals, for most veteran players** (62% of 2025's 170 players show a physically-impossible single-season `gamesPlayed`, up to 537) — dropped as a cross-check (decided in review round 3), replaced by an official-source spot-check as a pipeline acceptance step. A draft upstream issue is at `docs/upstream-issue-draft.md`. See §8.

---

## 1. Which seasons are present (2025, 2026 especially), and is 2026 complete

Checked by listing release assets directly (asset `updated_at` timestamps, not just the release's creation date, since these releases get new files added in place):

| Dataset | Seasons built | Notes |
|---|---|---|
| `player_box` (game-by-game) | 2002–2026, contiguous | `player_box_2026.csv/.parquet/.rds` last updated **2026-10-01 10:39 UTC** (today, this morning) |
| `player_season_stats` | 2002–2021, then **2023–2026** — **2022 is missing** | 2026 asset last updated 2026-10-01 10:41 UTC. Row counts climb day-by-day through the season (6,708 → 10,396 rows) as expected; one anomaly — the 2026-09-17 build logged only 43 rows before the 2026-09-18 build returned to 10,055 — a one-day blip, self-corrected. Sanity-check row counts rather than trust any single day's file blindly. |
| `player_core` (biographical) | not explicitly logged, 76 release assets, last updated 2026-10-01 | |
| `player_crosswalk` (cross-source ID map) | **2026 only** (1 season, 221 rows) | Doesn't help for 2025 or earlier, and doesn't include Unrivaled/AU ids — maps ESPN ↔ stats.wnba.com ↔ Fox ↔ Yahoo only |

**2026 regular-season completeness, confirmed directly from the data:** filtering `player_box_2026.csv` to `season_type == 2`, game dates run **2026-05-08 → 2026-09-24** across 113 distinct dates, with **zero games logged between 2026-08-31 and 2026-09-16** (the FIBA World Cup break window per `league-rules.md`). Postseason (`season_type == 3`) rows start 2026-09-27, matching "playoffs begin Sep 27." So the regular season is complete through the date range the analysis plan needs, and the break is real in the data, not just in the reference doc.

**FIBA Women's World Cup data: not available anywhere in sportsdataverse, checked directly.** `wehoop-wnba-data`'s own build scripts (`python/espn_wnba_01..16_*.py`) only touch ESPN's WNBA endpoints (schedules, pbp, boxscores, rosters, stats, standings, officials, shots, draft, crosswalks) — no FIBA/international step exists. A search of the `sportsdataverse` GitHub org for a FIBA-specific repo returned nothing. This isn't a gap to fix — `league-rules.md` already treats World Cup participation (51 WNBA players) as context to flag, not performance data to analyze, and there's no WNBA-adjacent source for it in this pipeline's data stack. Worth remembering if the project ever wants in-tournament stats: it would need a separate, non-sportsdataverse source.

**The 2022 gap in `player_season_stats` is real** — log in `docs/decisions.md` as a known data gap (already logged; see decisions log).

## 2. Season totals vs. game-by-game box scores, and columns

Both exist, but they're shaped very differently:

- **`player_box`** — one row per player per game. Columns include `game_id`, `season`, `season_type` (2=regular, 3=postseason — see §6 for the All-Star wrinkle), `game_date`, `athlete_id`, `athlete_display_name`, `team_id`, `minutes`, full shooting/rebounding/assist/steal/block/turnover/foul/points splits, `starter`, `ejected`, `did_not_play`, `reason`, `active`, plus team and opponent metadata. Every component Game Score needs — `field_goals_made`, `field_goals_attempted`, `free_throws_made`, `free_throws_attempted`, `offensive_rebounds`, `defensive_rebounds`, `assists`, `steals`, `blocks`, `turnovers`, `fouls`, `points` — is present here directly.
- **`player_season_stats`** — **long format**: one row per `(season, athlete_id, stat_name)`, ~40 rows per player-season split across `category` = `averages` / `totals` / `miscellaneous`. ESPN pre-computes per-game averages and season totals, but there's no raw `totalMinutes` row, only `avgMinutes` (rounded to 1 decimal) and `gamesPlayed` — multiplying them compounds ESPN's rounding, whereas summing `minutes` from `player_box` is exact.
- **`team_box`** — one row per team per game (confirmed full column list): `field_goals_made/attempted`, `free_throws_made/attempted`, `three_point_*`, `offensive_rebounds`, `defensive_rebounds`, `total_rebounds`, `assists`, `steals`, `blocks`, `fouls`, `turnovers` / `team_turnovers` / `total_turnovers`, plus `game_id`/`game_date`/`team_id`. **No `minutes` column.** This matters for two measures below (team-minutes share, usage%) — team minutes have to come from summing `player_box.minutes` grouped by `(game_id, team_id)`, not from `team_box` directly.

**Recommendation (already logged as a decision, approved in PR #1 review)**: build per-game and per-40 stats by aggregating `player_box` game logs ourselves, rather than pivoting `player_season_stats`. More precise, same table for per-game and season-level work, sidesteps the 2022 gap.

## 3. Does `minutes` include overtime?

Yes — confirmed with real data.

**Method**: for each 2025 and 2026 game, summed `minutes` across all rows for one team. In regulation, a team's player-minutes sum to exactly 200 (5 players × 40 min) regardless of substitution pattern; each 5-minute OT period adds 25 team-minutes. Sums above ~205 flag OT games.

Found 16 such games in 2025 and 26 in 2026. Clearest case: **game `401857031`, Washington Mystics @ Portland Fire, 2026-06-28** — team sums were 302 and 300 minutes. ESPN's own game summary for that `game_id` shows a 124–123 final with **8 periods** (4 quarters + 4 overtimes): 200 + 4×25 = 300, exactly matching the Fire's summed minutes (Mystics' 302 is off by 2, consistent with per-player rounding). Smaller cases (sums of 225–226, consistent with 1 OT) appeared in both seasons.

## 4. Are did-not-play reasons included, and is this consistent across seasons?

Yes, as `did_not_play` (bool) and `reason` (string) — now spot-checked across **four** seasons (2023, 2024, 2025, 2026), not just two:

| Season | DNP rows | DNP rows w/ blank reason | Played rows w/ non-blank `reason` (the junk pattern) | Boolean casing |
|---|---:|---:|---:|---|
| 2023 | 852 | 0 | 4,935 of 4,944 (99.8%) | `TRUE`/`FALSE` |
| 2024 | 971 | 0 | 4,953 of 4,958 (99.9%) | `TRUE`/`FALSE` |
| 2025 | — (see first pass) | — | 2025-specific detail in first-pass notes below | `TRUE`/`FALSE` |
| 2026 | 1,447 | 1 | 6,791 of 6,799 (99.9%) | `true`/`false` |

- Every DNP row has a `reason` in all four seasons (blank only once, in 2026). The reason strings themselves are genuinely useful on DNP rows: `"COACH'S DECISION"` plus a long tail of specific injury/illness/personal strings (`"LEFT KNEE INJURY"`, `"CONCUSSION PROTOCOL"`, `"SUSPENDED BY LEAGUE"`, `"NOT WITH TEAM - PREGNANCY"`, etc.).
- **But `reason == "COACH'S DECISION"` is also stamped on essentially all *played* rows that have a non-blank reason** — confirmed in 2023 and 2024 at the same ~99%+ rate as 2025/2026 (e.g., a player logging 30+ minutes can still carry `reason = "COACH'S DECISION"`). This is a durable, multi-season characteristic of the source, not a one-off. **Rule for the pipeline: only read `reason` when `did_not_play == true`.**
- **Boolean-casing trap confirmed to be a 2026-only change**, not spread across years: 2023, 2024, and 2025 all use uppercase `TRUE`/`FALSE`; only 2026 uses lowercase `true`/`false`. Still a real trap for any CSV-string-comparison code, and still avoided entirely by reading `.parquet` (typed booleans).

## 5. Player identification and matching to our offseason list

- Players are identified by a stable, numeric ESPN `athlete_id`. Spot-checked four well-known players (A'ja Wilson, Caitlin Clark, Breanna Stewart, Napheesa Collier) across 2025 and 2026 — same `athlete_id` both years for all four, no `(game_id, athlete_id)` duplicates, no same-season display-name collisions.
- `player_core` adds biographical fields keyed on `athlete_id` (`full_name`, `date_of_birth`, `college_id`, `height`, `draft_year`) — usable for disambiguating shared names, and (per the new context-field check in §6/the measure table) for computing age.
- `player_crosswalk` does ESPN ↔ stats.wnba.com ↔ Fox ↔ Yahoo matching with its own `match_method`/`match_confidence` — a good pattern to borrow — but only covers **2026** and has no concept of Unrivaled/AU/overseas.
- `data/raw/offseason_assignments.csv` still doesn't exist yet. Plan unchanged from the first pass: match primarily on normalized player name, use `player_core` (DOB/college) to break ties, and carry our own `match_confidence`/`match_method` columns (already logged as a decision, approved in PR #1 review).

## 6. `season_type`: regular season vs. postseason, and the All-Star wrinkle

`season_type == 2` is regular season, `season_type == 3` is postseason — confirmed by the 2026 date ranges in §1 (regular season through Sep 24, postseason starting Sep 27, no overlap). **The analysis uses `season_type == 2` only**; postseason games should be excluded from per-game/per-40 rollups so a short playoff run doesn't skew a player's post-offseason numbers.

**New finding while checking team-change and team-minutes feasibility**: the All-Star Game is *also* tagged `season_type == 2`, not given its own type or excluded. It uses fictitious team rosters with their own `team_id`s:

- 2025: `TEAM CLARK` (`team_id` 131246), `TEAM COLLIER` (131247)
- 2026: `TEAM SPOON` (133383), `TEAM COOP` (133384)

Grouping naively by `athlete_id` + `team_id` within `season_type == 2` therefore finds players with ">1 team" for two different reasons that need to be told apart: the All-Star artifact, and genuine in-season trades. Checked both:

- **All-Star artifact**: of 51 "multi-team" 2025 players and 45 in 2026, 25 and 22 respectively have one of their "teams" matching the `^TEAM ` naming pattern — e.g., A'ja Wilson shows up under both Las Vegas (`team_id` 17) and `TEAM CLARK` (131246).
- **Genuine trades, confirmed with a real example**: Aneesah Morrow's 2026 game log shows a clean split — Connecticut Sun (`team_id` 18) for every game through 2026-07-30, then Toronto Tempo (`team_id` 131935) for every game from 2026-08-02 onward, against a full spread of different opponents both before and after. This is an actual mid-season trade, not a data artifact.

**Implication**: any measure that groups by team per player-season — games-played share, team-minutes share, team-change detection — needs to exclude rows where `team_display_name` matches `^TEAM ` (or an explicit excluded `team_id` list) *before* grouping. This isn't optional cleanup; left in, it would make most All-Stars look like they were traded to a team that doesn't actually exist on their schedule.

---

## Per-measure support (against the CLAUDE.md analysis plan + league-rules.md context notes)

| Measure | Supported? | Source | Notes |
|---|---|---|---|
| Minutes (per-game, per-40) | ✅ | `player_box.minutes`, summed/aggregated ourselves | Includes OT (§3). Sum from game logs rather than trusting `avgMinutes` precision. |
| Points, rebounds, assists (per-game, per-40) | ✅ | `player_box.points` / `.rebounds` / `.assists` | Direct; per-40 = total ÷ total minutes × 40. |
| TS% | ✅ (derived) | `points`, `field_goals_attempted`, `free_throws_attempted` from `player_box` | `PTS / (2 × (FGA + 0.44 × FTA))`. No upstream column — computed. |
| **Game Score, per-40** | ✅ (derived) | `player_box`: `field_goals_made`, `field_goals_attempted`, `free_throws_made`, `free_throws_attempted`, `offensive_rebounds`, `defensive_rebounds`, `assists`, `steals`, `blocks`, `turnovers`, `fouls`, `points` | Every component of Hollinger's formula (`PTS + 0.4·FGM − 0.7·FGA − 0.4·(FTA−FTM) + 0.7·OREB + 0.3·DREB + STL + 0.7·AST + 0.7·BLK − 0.4·PF − TOV`) is present in `player_box` — confirmed column-by-column, nothing missing. Compute the raw total per player-season, then scale by minutes to get a per-40 rate the same way as the other per-40 stats. |
| Usage% | ✅ (derived, extra join) | `player_box` (player FGA/FTA/TOV/minutes) + `team_box` (team FGA/FTA/TOV) + team minutes from summed `player_box` | `team_box` has no `minutes` column (§2) — team minutes must come from summing `player_box.minutes` by `(game_id, team_id)`, same denominator used for team-minutes share below. `team_box` has three turnover-ish columns (`turnovers`, `team_turnovers`, `total_turnovers`) — pick one deliberately (likely `total_turnovers`, team + individual) and log it as a decision rather than guessing silently. |
| Share of games played | ✅ (derived) | `player_box`/`team_box`, `season_type == 2` only, **All-Star rows excluded (§6)** | `player's distinct game_ids in season ÷ team's distinct game_ids in season`. Needs the All-Star filter or it under/over-counts team games for anyone who made an All-Star team. |
| Share of team minutes | ✅ (derived) | `player_box` only — team minutes summed from player rows, not from `team_box` (§2) | `player's total minutes ÷ sum of all players' minutes for that team that season`. Same All-Star exclusion applies. |
| First-half vs. second-half splits, by games played | ✅ (derived) | `team_box` for the team's full game sequence (`game_id`, `game_date`, `team_id`) + `player_box` for the player's per-game stats | Per `league-rules.md` point 4: split by **count of the team's games played**, not calendar date, because the World Cup break (confirmed real in §1) splits the 2026 season unevenly in time. Need the team's full schedule (including games the player sat out) to correctly number "the team's Nth game" — that's why this needs `team_box`, not just the player's own rows. Exclude All-Star "team" game_ids from the real team's sequence (they already live under a different `team_id`, so no contamination here). |
| Age (context) | ✅ (derived) | `player_core.date_of_birth` (ISO-ish string, e.g. `1987-08-21T07:00Z`) | Recommend computing age as of a fixed reference date per season (e.g., the season's opening day) from `date_of_birth`, rather than trusting `player_core.age`, which is frozen at whatever moment that season's file was last built and isn't guaranteed to mean "age on opening day." |
| Team change (context) | ✅ (derived) | `player_box.team_id` compared across the offseason boundary / within a season | Must exclude All-Star artifact rows first (§6) — confirmed a real trade (Aneesah Morrow, Sun → Tempo, 2026) is distinguishable from the All-Star artifact by checking whether the "other team" name matches `^TEAM `. |
| Games played / minutes threshold filtering | ✅ | `player_box`, grouped by player-season, `season_type == 2`, All-Star excluded | Straightforward once the per-40 aggregation and All-Star filter both exist. |
| Season totals as a cross-check | ❌ dropped (§8) | — | `player_season_stats` holds career totals for most veteran players, not season totals (§8) — not usable as a cross-check. Replaced by an official-source (WNBA.com/Basketball-Reference) spot-check for 5–10 players, added as a pipeline acceptance step. |
| Offseason league → WNBA season join | ⚠️ not yet testable | `data/raw/offseason_assignments.csv` (doesn't exist yet) + `player_core`/`athlete_id` | Name-based matching; no upstream crosswalk covers offseason leagues (§5). |
| FIBA World Cup performance data | ❌ not available | — | Confirmed no FIBA/international dataset exists in sportsdataverse (§1). Not a blocker for the current plan — `league-rules.md` only wants WWC participation flagged as context, not analyzed as performance. |

---

## 7. Commissioner's Cup: how it's tagged, and whether its championship game counts toward regular-season totals — reporting back, not deciding

Checked the `schedules` dataset's `notes_headline` field (ESPN's own event-note text) for both 2025 and 2026, then cross-referenced the flagged games against `player_box`.

**Group-play Commissioner's Cup games** (`notes_headline == "WNBA Commissioner's Cup"`, 36 games in 2025, 37 in 2026) are **ordinary regular-season games** — real opponents, normal rosters, `season_type == 2`, and they're part of each team's normal 44-game slate (confirmed: a non-finalist team's full-season game count is unaffected by them). Nothing special needed here; they're indistinguishable from any other regular-season game once you've counted them, which is correct since they *are* regular-season games that happen to also count toward Commissioner's Cup group standings.

**The Commissioner's Cup Championship Game is a different story.** Found it by its own `notes_headline` value (`"WNBA Commissioner's Cup Championship"`) — one game per year: `game_id 401736430` (Lynx 59 – Fever 74, 2025-07-01) and `game_id 401857321` (Liberty 93 – Aces 85, 2026-06-30). Checked whether it's inside or outside each finalist's normal 44-game slate by comparing distinct `season_type == 2` game counts:

| Team | Season | Distinct `season_type==2` games | Includes championship game? |
|---|---|---:|---|
| Minnesota Lynx (2025 finalist) | 2025 | **45** | Yes |
| Indiana Fever (2025 finalist) | 2025 | **45** | Yes |
| Seattle Storm (2025 non-finalist) | 2025 | 44 | — |
| New York Liberty (2026 finalist) | 2026 | **45** | Yes |
| Las Vegas Aces (2026 finalist) | 2026 | **45** | Yes |
| Seattle Storm (2026 non-finalist) | 2026 | 44 | — |
| Toronto Tempo (2026 non-finalist) | 2026 | 44 | — |

So: **the Championship Game is tagged `season_type == 2`, identical to a real regular-season game, uses real teams and real rosters (unlike the All-Star Game, no fake `team_id`), and its stats are fully included in `player_box`/`team_box` as an extra, 45th game — only for the two finalists.** It is not inside the normal 44; it's additive. Confirmed consistently for both the 2025 and 2026 finalists.

**Resolved in PR #1 review round 3 — excluded, verified against official stats.** Decision and the verification method are logged in full in `docs/decisions.md`. Short version: compared Napheesa Collier's (2025 Lynx, a finalist) full `player_box` game log against her official Basketball-Reference/ESPN 2025 season line. Her log has 35 nominal `season_type == 2` played games — 33 real Lynx games, plus the Championship Game and her All-Star Game appearance. Removing both non-regular-season rows and summing the remaining 33 produces an **exact** match on every stat checked (games, points, rebounds, assists, minutes, steals, blocks) to the official record. So the Championship Game is excluded from analysis the same way the All-Star Game is, just identified differently: by `game_id`, joined from `schedules.notes_headline == "WNBA Commissioner's Cup Championship"` (no team-name pattern available here, since real rosters are used).

## 8. Critical new finding: `player_season_stats` contains career totals for most veteran players, not season totals

Found this while sanity-checking the Commissioner's Cup games-played counts against `player_season_stats`, and it's bigger than the original 2022-gap finding — **it affects whether `player_season_stats` is usable at all, even as a cross-check.**

Checked Napheesa Collier's row in `player_season_stats_2025.csv`: `gamesPlayed = 193`, `totals.points = 3542`. No WNBA player has played 193 games in a single season — that's close to her actual **career** game count (she entered the league in 2019). `avgPoints` (18.4) × `gamesPlayed` (193) ≈ `totals.points` (3542), so the whole row is internally consistent — just consistently a **career** total, not a 2025 season total, despite living in the file named `player_season_stats_2025.csv` and being keyed `season == 2025`.

Checked how widespread this is: of the 170 players with a `gamesPlayed` row in `player_season_stats_2025.csv`, **105 (62%) show `gamesPlayed` above 45** — physically impossible for a single WNBA season, so very likely career totals mislabeled as season totals. The max is 537 (DeWanna Bonner, a long-tenured veteran — consistent with a career count). Players with low career-game counts (rookies, players who just returned from injury) would show a "plausible" single-season-sized number even if it's actually their career total, so this likely isn't limited to the 105 I can prove — it's just the 105 I can *prove* with this one sanity check.

**Resolved in PR #1 review round 3 — `player_season_stats` dropped as a cross-check.** Logged as a reversal in `docs/decisions.md` (it supersedes part of the earlier per-40 decision, which had proposed keeping it as a cross-check). Replacement: once the pipeline exists, spot-check its output against official season totals (WNBA.com or Basketball-Reference) for 5–10 players as a required pipeline acceptance step — the same method that verified the Commissioner's Cup exclusion above. A draft GitHub issue describing this problem for the upstream repo is at `docs/upstream-issue-draft.md`, for Chloe to review and post herself.

## Open items

**Already logged in `docs/decisions.md` and approved:**
1. Derive 2022 `player_season_stats` from `player_box` game logs rather than waiting on upstream (round 1).
2. Build per-game/per-40 stats from `player_box`, not by pivoting `player_season_stats` (round 1).
3. Read `.parquet`, not `.csv`, to avoid the boolean-casing inconsistency (round 1).
4. Match offseason assignments to players by name, with a logged `match_method`/`match_confidence`, not by ID (round 1).
5. Exclude All-Star Game rows (`team_display_name` matching `^TEAM `) before computing any team-grouped measure (round 2).
6. Usage%'s team-turnover input is `team_box.total_turnovers`, verified empirically against all 624 2025 team-game rows (round 2).
7. Exclude the Commissioner's Cup Championship Game, identified via `schedules.notes_headline`; verified against official 2025 stats for a finalist (round 3).
8. Reversal: drop `player_season_stats` as a cross-check; replace with an official-source spot-check as a pipeline acceptance step (round 3).

**Still open, needs your call:**

9. **Age reference point** — compute from `player_core.date_of_birth` against each season's opening day, rather than using the pre-baked `player_core.age` column (frozen at build time, not a comparable fixed point). Not yet approved.

## What I didn't do (by design, per the task)

- Didn't download full historical data (2002–2022, beyond the four seasons spot-checked) or any `pbp`/`shots`/`rosters` datasets — out of scope for this audit.
- Didn't write any pipeline code or touch `data/raw/` or `data/clean/`.
- Didn't pull `team_box` CSVs to verify row-level values (only confirmed its column list and the absence of a `minutes` column against the data dictionary) — worth a closer look once the pipeline actually builds team-minutes/usage logic.
