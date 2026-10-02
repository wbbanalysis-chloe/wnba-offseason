# Data audit: sportsdataverse/wehoop-wnba-data

_Audited 2026-10-01. Checked via the GitHub API/CLI against the `wehoop-wnba-data` repo (data dictionaries in `docs/datasets/*.md`) and the `sportsdataverse-data` releases that actually hold the files. Spot-checks ran against downloaded `player_box_2025.csv` and `player_box_2026.csv` (and a sample of `player_season_stats_2025.csv`) in a scratch directory — nothing was added to this repo. No pipeline code was written._

## TL;DR

- **2025 and 2026 are both present and current** in the per-game player box scores (`player_box`), refreshed as of today. Good to build on.
- **Season totals (`player_season_stats`) have a real gap: 2022 is missing entirely.** This is almost certainly the "open issue about updates" CLAUDE.md flags — confirmed, not hypothetical.
- Per-game box scores exist with a rich column set, including `did_not_play` and `reason`. Season totals are a separate, **long-format** table (one row per stat, not one row per player-season) with per-game averages and totals already computed by ESPN.
- **Minutes do include overtime.** Confirmed with a real 4-OT game (two WNBA expansion teams, June 28, 2026) where summed player-minutes per team (300–302) matched 4 OT periods exactly.
- **`reason` is unreliable unless you filter on `did_not_play == true` first** — it's populated with `"COACH'S DECISION"` on thousands of rows where the player actually played real minutes. Looks like a default/carried-over ESPN value, not a DNP-specific field.
- **Boolean columns are serialized inconsistently across season CSVs**: `TRUE`/`FALSE` in 2025, `true`/`false` in 2026. A silent trap if the pipeline reads CSV strings naively (I hit it in the audit script itself). Parquet avoids this because booleans are typed — recommend reading parquet, not CSV, in the pipeline.
- **Players are identified by stable ESPN `athlete_id`s** that persist across seasons (spot-checked 4 well-known players) and don't collide within a season. There is a `player_crosswalk` dataset that maps ESPN ids to stats.wnba.com/Fox/Yahoo ids with a match-confidence score — but it's **only built for 2026** and doesn't cover Unrivaled or Athletes Unlimited at all. Matching our hand-built offseason CSV to `athlete_id` will have to be name-based, with `player_core` (DOB, college, height) as a disambiguator.

---

## 1. Which seasons are present (2025, 2026 especially)

Checked by listing release assets directly (asset `updated_at` timestamps, not just the release's creation date, since these releases get new files added in place):

| Dataset | Seasons built | Notes |
|---|---|---|
| `player_box` (game-by-game) | 2002–2026, contiguous | `player_box_2026.csv/.parquet/.rds` last updated **2026-10-01 10:39 UTC** (today, this morning) |
| `player_season_stats` | 2002–2021, then **2023–2026** — **2022 is missing** | 2026 asset last updated 2026-10-01 10:41 UTC. The dataset's own coverage log (`docs/datasets/player_season_stats.md`) shows row counts climbing day-by-day through the season (6,708 → 10,396 rows) as more players accumulate stats — expected, not a bug. One anomaly: the 2026-09-17 build logged only 43 rows before the next build (2026-09-18) returned to 10,055 — a one-day blip, self-corrected, but a reminder to sanity-check row counts rather than trust any single day's file blindly. |
| `player_core` (biographical) | not explicitly logged, but 76 release assets present, last updated 2026-10-01 | |
| `player_crosswalk` (cross-source ID map) | **2026 only** (1 season, 221 rows) | Doesn't help for 2025 or earlier, and doesn't include Unrivaled/AU ids — it maps ESPN ↔ stats.wnba.com ↔ Fox ↔ Yahoo only |

**The 2022 gap in `player_season_stats` is real and worth logging in `docs/decisions.md`** as a known data gap, with the alternative: derive season totals for 2022 ourselves by aggregating `player_box` game logs for that year (which *is* complete) instead of waiting on upstream to backfill.

## 2. Season totals vs. game-by-game box scores, and columns

Both exist, but they're shaped very differently:

- **`player_box`** — one row per player per game. Columns include `game_id`, `season`, `season_type` (2=regular, 3=postseason), `game_date`, `athlete_id`, `athlete_display_name`, `team_id`, `minutes`, full shooting/rebounding/assist/steal/block/turnover/foul/points splits, `starter`, `ejected`, `did_not_play`, `reason`, `active`, plus team and opponent metadata (names, colors, logos, score, home/away). This is the right table to build per-game and per-36 stats from.
- **`player_season_stats`** — **long format**: one row per `(season, athlete_id, stat_name)`, not one row per player-season. A single player-season is ~40 rows split across `category` = `averages` / `totals` / `miscellaneous`. ESPN pre-computes per-game averages (`avgPoints`, `avgMinutes`, `avgRebounds`, etc.) and season totals (`points`, `assists`, `fieldGoalsMade-fieldGoalsAttempted`, etc.) — confirmed by downloading and inspecting one player's full set of rows. There's no raw `totalMinutes` row, only `avgMinutes` (already rounded to 1 decimal) and `gamesPlayed` — so if we want total minutes played, multiplying `avgMinutes × gamesPlayed` compounds ESPN's rounding, whereas summing `minutes` straight from `player_box` is exact.

**Recommendation to log as a decision**: build per-game and per-36 stats by aggregating `player_box` game logs ourselves (sum minutes/points/etc., divide by games played or minutes), rather than pivoting `player_season_stats`. It's more precise, it's the same table for both per-game-level detail and season rollups, and it sidesteps the 2022 gap in `player_season_stats` entirely. `player_season_stats` is still useful as a cross-check against our own rollups.

- **TS% and usage%** are not provided directly by either table. TS% is cheaply derivable from `player_box`/`player_season_stats` totals (`points`, `field_goals_attempted`, `free_throws_attempted`). **Usage% needs team-level totals** (team minutes, FGA, FTA, TOV) for the formula's denominator — those exist in `team_box` / `team_season_stats` (same long-format shape, confirmed columns exist), so it's a join away, not a blocker, but it's an extra table the pipeline needs to pull in.

## 3. Does `minutes` include overtime?

Yes — confirmed with real data, not just inference from the column description (which just says "Minutes played," no mention of OT either way).

**Method**: for each 2025 and 2026 game, summed `minutes` across all rows for one team. In regulation, 5 players are on the floor for all 40 minutes, so a team's player-minutes should sum to exactly 200 regardless of substitution patterns. Each 5-minute OT period adds 25 team-minutes (5 players × 5 min). So team-minute sums above ~205 (allowing ±1-2 for ESPN's own rounding) flag OT games.

Found 16 such games in 2025 and 26 in 2026. The clearest case: **game `401857031`, Washington Mystics @ Portland Fire, 2026-06-28** — team sums were 302 and 300 minutes. I checked ESPN's own game summary for that `game_id` directly: the final score was 124–123, and the line score had **8 periods** (4 quarters + 4 overtimes). 200 (regulation) + 4 × 25 (OT) = 300 — exactly matching the Fire's summed minutes (Mystics' 302 is off by 2, consistent with normal per-player rounding to the nearest whole minute). This is about as direct a confirmation as a spot-check gets without play-by-play data.

Smaller cases (team sums of 225–226, consistent with 1 OT) appeared in both seasons, so this isn't a one-off.

## 4. Are did-not-play reasons included?

Yes, as `did_not_play` (bool) and `reason` (string) — but `reason` needs guarding:

- In 2025, `reason` on `did_not_play == true` rows is genuinely useful: 647 `"COACH'S DECISION"`, plus a long tail of specific injury/illness strings (`"LEFT KNEE"`, `"CONCUSSION PROTOCOL"`, `"ACL"`, `"NOT WITH TEAM - PREGNANCY"`, `"SUSPENDED BY LEAGUE"`, etc. — about 70 distinct values).
- **But `reason` is also populated on rows where the player actually played.** In the 2026 file, 6,791 rows with `did_not_play == false` still carry `reason == "COACH'S DECISION"` — including players who logged 30+ minutes (e.g., Naz Hillmon, 33 minutes, `reason = "COACH'S DECISION"`). This looks like a default/carried-over value from the ESPN source feed, not a real signal, on played rows.
- **Rule for the pipeline**: only read `reason` when `did_not_play == true`. Don't use `reason` as a general-purpose flag.
- Separately, note the **boolean-casing trap**: `did_not_play`/`starter`/`ejected`/`active` are `"TRUE"/"FALSE"` (uppercase) in the 2025 CSV and `"true"/"false"` (lowercase) in the 2026 CSV. My first pass at this audit script silently returned zero DNPs for 2026 because it only matched the uppercase string. This will bite a pandas pipeline reading CSVs with naive string comparisons. **Reading the `.parquet` files instead of `.csv` sidesteps this** — parquet stores these as typed booleans, not case-variable strings.

## 5. Player identification and matching to our offseason list

- Players are identified by a stable, numeric ESPN `athlete_id`. Spot-checked four well-known players (A'ja Wilson, Caitlin Clark, Breanna Stewart, Napheesa Collier) across the 2025 and 2026 files — same `athlete_id` both years for all four. No `(game_id, athlete_id)` duplicates, no same-season display-name collisions mapping to two different ids, in either file.
- `player_core` adds biographical fields keyed on `athlete_id` (`full_name`, `date_of_birth`, `college_id`, `height`, `draft_year`) — useful for disambiguating two players who share a name.
- There **is** a `player_crosswalk` dataset that does ESPN ↔ stats.wnba.com ↔ Fox ↔ Yahoo matching, with its own `match_method` and `match_confidence` columns — a good pattern to borrow — but it **only covers the 2026 season (221 rows)** and only maps WNBA-side ID systems. It has no concept of Unrivaled, Athletes Unlimited, or overseas leagues, so it won't help join `data/raw/offseason_assignments.csv` directly.
- **`data/raw/offseason_assignments.csv` doesn't exist yet**, so this is a forward-looking design point rather than something I could test against real data. CLAUDE.md specs it with `player_name, player_id` columns, but doesn't say what `player_id` namespace that is — if it's going to be hand-compiled from a source like the WNBA Offseason Player Tracker blog post, it almost certainly won't carry ESPN ids. **Realistic plan: match primarily on normalized player name, use `player_core` (DOB/college) to break ties on shared names, and carry a `match_confidence`/`match_method` column in our own join output** (mirroring what `player_crosswalk` does) so mismatches are auditable rather than silent.

---

## Per-measure support

| Measure | Supported? | Source | Notes |
|---|---|---|---|
| Minutes (per-game, per-36) | ✅ | `player_box.minutes`, summed/aggregated ourselves | Includes OT (confirmed §3). Sum from game logs rather than trusting `avgMinutes` precision. |
| Points | ✅ | `player_box.points` | Direct. |
| Rebounds | ✅ | `player_box.rebounds` (+ off/def splits) | Direct. |
| Assists | ✅ | `player_box.assists` | Direct. |
| TS% | ✅ (derived) | `points`, `field_goals_attempted`, `free_throws_attempted` from `player_box` | Standard formula: `PTS / (2 × (FGA + 0.44 × FTA))`. No upstream column — we compute it. |
| Usage% | ✅ (derived, extra join) | `player_box` (player FGA/FTA/TOV/minutes) + `team_box` (team FGA/FTA/TOV/minutes) | Needs a team-level join, not just the player table. Confirmed `team_box`/`team_season_stats` exist with the needed columns; didn't download/verify team files in this pass since no analysis step needed it yet. |
| Games played / minutes threshold filtering | ✅ | `player_box`, grouped by player-season | Straightforward once per-36/per-game aggregation exists. |
| Season totals as a cross-check | ⚠️ partial | `player_season_stats` | Usable 2002–2021 and 2023–2026; **2022 is missing** (§1). Fine as a sanity check against our own `player_box` rollups, not as the primary source. |
| Offseason league → WNBA season join | ⚠️ not yet testable | `data/raw/offseason_assignments.csv` (doesn't exist yet) + `player_core`/`athlete_id` | Will be name-based matching; no upstream crosswalk covers offseason leagues (§5). |

---

## Open items to log in `docs/decisions.md`

1. **2022 `player_season_stats` gap** — alternative considered: wait for upstream backfill vs. derive 2022 season totals from `player_box` ourselves. Recommend the latter so the pipeline doesn't stall on an external repo's open issue.
2. **Per-game/per-36 source of truth** — alternative considered: pivot `player_season_stats` (ESPN's pre-computed averages) vs. aggregate `player_box` game logs ourselves. Recommend aggregating `player_box` for precision and consistency across the 2022 gap.
3. **Read parquet, not CSV** — alternative considered: CSV for simplicity vs. parquet for typed, consistent booleans. Recommend parquet given the demonstrated `TRUE/FALSE` vs `true/false` inconsistency.
4. **Offseason-to-WNBA player matching** — alternative considered: wait for/build an ESPN-id-aware crosswalk vs. name-based matching with a confidence/method column. Recommend the latter, since no existing crosswalk covers Unrivaled/AU/overseas, and log match confidence so weak matches are reviewable rather than silent.

## What I didn't do (by design, per the task)

- Didn't download full historical data (2002–2024) or any `pbp`/`shots`/`rosters` datasets — out of scope for this audit.
- Didn't write any pipeline code or touch `data/raw/` or `data/clean/`.
- Didn't verify `team_box`/`team_season_stats` columns beyond confirming they exist and hold the fields usage% needs — worth a closer look once the pipeline actually builds usage%.
