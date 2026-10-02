# Decisions

Assumptions and method choices that shape the findings, logged as they're made. Each entry: the decision, why, and the alternative considered. See `docs/data-audit.md` for the data audit these first four came out of.

## 2026-10-01 — Derive 2022 season totals from `player_box`, don't wait on upstream

`sportsdataverse/wehoop-wnba-data`'s `player_season_stats` dataset is missing the 2022 season entirely (every other season from 2002–2026 is present). Rather than blocking on an upstream backfill, the pipeline will derive 2022 player-season totals by aggregating `player_box` game logs for that year, which **is** complete.

**Alternative considered:** wait for/file an issue against upstream and hold off on 2022 until it's backfilled. Rejected because it blocks the pipeline on someone else's timeline for a gap we can fill ourselves from data we already have.

## 2026-10-01 — Build per-game and per-36 stats from `player_box`, not by pivoting `player_season_stats`

`player_season_stats` is long-format (one row per stat) and only exposes ESPN's pre-rounded `avgMinutes`/per-game averages, not raw total minutes. Multiplying `avgMinutes × gamesPlayed` would compound that rounding. The pipeline will instead sum `minutes`, `points`, etc. directly from `player_box` game logs per player-season, which is exact and uses the same source table end to end.

**Alternative considered:** pivot `player_season_stats`'s long format into per-player-season rows and use ESPN's own averages/totals directly. Rejected for precision (rounding compounds) and because it doesn't cover 2022 (see above) — `player_season_stats` will still be used as a cross-check against our own rollups, not as the primary source.

## 2026-10-01 — Read `.parquet`, not `.csv`, from wehoop-wnba-data releases

Boolean columns (`did_not_play`, `starter`, `ejected`, `active`) are serialized inconsistently across season CSVs — `TRUE`/`FALSE` (uppercase) in the 2025 file, `true`/`false` (lowercase) in the 2026 file. A naive string comparison reading CSVs will silently miss rows (this bit the audit script itself). Parquet stores these as typed booleans and avoids the casing trap.

**Alternative considered:** read CSV for simplicity (no parquet library dependency) and normalize boolean strings ourselves. Rejected — reading parquet removes the failure mode entirely instead of patching around it, and pandas reads parquet natively.

## 2026-10-01 — Match offseason assignments to WNBA players by name, with a logged confidence/method, not by ID

`data/raw/offseason_assignments.csv` doesn't exist yet, and when it's built (likely from a source like the WNBA Offseason Player Tracker blog post) it almost certainly won't carry ESPN `athlete_id`s. The only existing cross-source ID crosswalk in wehoop-wnba-data (`player_crosswalk`) covers 2026 only and doesn't know about Unrivaled, Athletes Unlimited, or overseas leagues at all. The join will be primarily name-based, using `player_core` (date of birth, college) to disambiguate players who share a name, and will carry its own `match_method`/`match_confidence` columns (mirroring `player_crosswalk`'s pattern) so weak or ambiguous matches are visible and reviewable rather than silently wrong.

**Alternative considered:** wait for or build a dedicated ID crosswalk that spans offseason leagues before doing any matching. Rejected — no such crosswalk exists today and building one is its own project; logging match confidence lets us ship the name-based join now while keeping bad matches auditable.
