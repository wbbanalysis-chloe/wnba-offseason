# WNBA Offseason Impact

## What this project is
A public portfolio project by Chloe Barroukh (GitHub: wbbanalysis-chloe).

**Research question:** Does where a WNBA player spends her offseason — Unrivaled, Athletes Unlimited, overseas, or resting — change how she performs in the following WNBA season?

The end product is a live web app where anyone can pick a player (or a group of players) and compare their WNBA performance before and after each type of offseason, plus a written summary of findings in the README.

## Working agreement
- **I own the decisions.** Metric definitions, data joins, inclusion rules, and anything that shapes the findings are mine. Propose options with tradeoffs; don't pick silently.
- **Show your reasoning.** Before writing or changing a file, summarize what it does and why this approach. Flag anything non-obvious in the code itself.
- **Everything goes through review.** One branch per task, small focused pull requests, and nothing merges to `main` until I've reviewed it.
- **Stay in scope.** Don't refactor or restyle code outside the task at hand.
- **Make assumptions visible.** If a data source, join, or method is uncertain, say so and log it in `docs/decisions.md` with the alternative considered.
- **Verify before claiming.** Check outputs against the source data (row counts, spot checks on known players) before calling a step done.

## Stack
- **Data pipeline:** Python 3 (pandas). Scripts live in `pipeline/`. Raw data in `data/raw/` (git-ignored if large), cleaned output as JSON/CSV in `data/clean/`.
- **Web app:** Next.js (App Router) + TypeScript + Tailwind CSS. Charts with Recharts.
- **Deploy:** Vercel, connected to the wbbanalysis-chloe GitHub account.
- No database for v1 — the app reads the cleaned JSON files.

## Data sources
- **WNBA box scores and player stats:** sportsdataverse `wehoop-wnba-data` (https://github.com/sportsdataverse/wehoop-wnba-data). Check that the most recent season is present before relying on it; there's an open issue about updates.
- **Offseason assignments (who played where each winter):** hand-compiled CSV at `data/raw/offseason_assignments.csv` with columns `player_name, player_id, offseason_year, league, team, source_url`. Leagues: `unrivaled`, `athletes_unlimited`, `overseas`, `none`.
- Unrivaled seasons: 2025 (inaugural) and 2026. Note every source URL so the dataset is auditable.

## Method (v1)
- Compare per-game and per-36 stats (points, rebounds, assists, TS%, usage, minutes) in the WNBA season *before* vs. *after* each offseason.
- Minimum minutes threshold to avoid tiny samples (decide and document in `docs/decisions.md`).
- Show distributions and individual player deltas; don't overclaim causation — age, role changes, injuries and team changes all matter. Call that out in the app and README.

## Git workflow
- `main` is always deployable.
- One branch per task (`feat/pipeline-boxscores`, `feat/player-page`, `fix/...`), opened as a pull request and merged by me after review.
- Clear commit messages in the imperative ("Add per-36 stat calculation").
- Before any push, confirm the active GitHub account is wbbanalysis-chloe (`gh auth status`).

## Milestones
1. **Data:** pipeline pulls WNBA player season stats, joins offseason assignments, outputs `data/clean/player_seasons.json`.
2. **App v1:** Next.js page with player search and a before/after chart; league-level comparison view.
3. **Deploy:** live on Vercel with a link in the README.
4. **README:** question, data, method, findings, limitations, screenshots, live link.

## Commands
- Pipeline: `python pipeline/build.py`
- App: `npm run dev` (http://localhost:3000)
