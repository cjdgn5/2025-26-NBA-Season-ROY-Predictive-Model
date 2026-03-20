# 2025-26 NBA ROY Predictive Model

This project predicts NBA Rookie of the Year (ROY) candidates using historical and current-season player data.

## What This Pipeline Does

The workflow has 3 main steps:

1. Collect data  
Pull season player stats, identify rookies, and build ROY labels.

2. Prepare modeling data  
Create the final feature table used for training and scoring.

3. Train and score  
Train the model, evaluate it, and export current-season rankings.

## High-Level Workflow

### 1) Data Collection (`src/data_collection.py`)
- Pulls/caches season-level stats from `nba_api`
- Detects rookies by season
- Labels ROY winners using season-level and player-level caches
- Writes:
  - `data_processed/raw_season_stats_all_seasons.csv`
  - `data_processed/rookies_labeled.csv`

### 2) Feature Prep (`src/prepare_data.py`)
- Builds model-ready features from rookie season rows
- Includes production, efficiency, usage, availability, team context, and rookie-relative rank features
- Writes:
  - `data_processed/roy_dataset.csv`

### 3) Training + Predictions (`src/train_model.py`)
- Trains model(s) and selects best CV performer
- Saves model artifact and run metadata
- Exports predictions for all seasons and the latest season
- Uses season-normalized race odds for presentation (sum to 1 within a season)
- Writes:
  - `outputs/roy_model.pkl`
  - `outputs/run_info.json`
  - `predictions/roy_predictions_all_seasons.csv`
  - `predictions/predictions.csv`

## Quick Start (CMD)

```cmd
pip install -r requirements.txt
pip install -r requirements_extra.txt
python src\data_collection.py
python src\prepare_data.py
python src\train_model.py
```

## Useful Re-Run Options

Refresh current-season stats:

```cmd
python src\data_collection.py --refresh-current-season-stats
```

Refresh all seasons:

```cmd
python src\data_collection.py --refresh-all-season-stats
```

## Output Summary

- `predictions/predictions.csv` is the latest-season prediction file.
- `predictions/roy_predictions_all_seasons.csv` contains historical + current model scores.
- `outputs/run_info.json` stores training metadata for reproducibility.

## Next Steps: UI Dashboard

The next project phase is a lightweight dashboard to present the ROY race in a clear, visual format.

Suggested first version:
- Show top 5 / top 10 rookies by season-normalized race odds
- Include a sortable table (player, team, odds, key features)
- Add one or two charts (for example: odds bar chart and trend line over refreshes)
- Add a "last updated" timestamp from the latest pipeline run

Suggested workflow:
1. Run the data pipeline on a schedule (daily or weekly).
2. Read `predictions/predictions.csv` as the primary dashboard source.
3. Render dashboard visuals and publish updates automatically.
