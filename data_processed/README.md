This folder contains processed datasets used by the ROY pipeline.

## Files

- `raw_season_stats_all_seasons.csv`  
Full season-level stats pulled from collection step.

- `rookies_labeled.csv`  
Rookie-only rows with ROY labeling.

- `roy_dataset.csv`  
Final model-ready dataset with engineered features and `label` (`1=ROY`, `0=not`).

## Data Flow

1. `raw_season_stats_all_seasons.csv` is created in data collection.
2. Rookie filtering + ROY labeling creates `rookies_labeled.csv`.
3. Feature engineering + preflight checks creates `roy_dataset.csv`.

## Feature Buckets in `roy_dataset.csv`

- Availability/volume: `GP`, `MIN`, `TOTAL_POINTS`, `TOTAL_MINUTES`, `MIN_per_game`
- Box production: per-game and per-75 metrics
- Efficiency/usage: `TS`, `FG3_PCT`, `USG_RATE`, `TOV`
- Team context: `TEAM_WIN_PCT`, `MINUTES_SHARE`, `POINTS_SHARE`
- Rookie-relative context: seasonal rookie rank features (production/usage/team success)
- Player context: `DRAFT_PICK_LOG`, `AGE_OCT1`

## Validation Notes

Before writing `roy_dataset.csv`, preflight checks fail fast on:
- missing required columns
- duplicate `PLAYER_ID + SEASON`
- completed seasons without exactly 1 ROY label

These checks help prevent training on broken data.
