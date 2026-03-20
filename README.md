# 2025-26-NBA-Season-ROY-Predictive-Model

NBA Rookie of the Year (ROY) prediction pipeline built with `nba_api` and scikit-learn.

## Overview

This repository contains an end-to-end workflow that:
- Collects historical season and player data from NBA Stats endpoints
- Identifies rookies by season
- Labels ROY winners
- Engineers modeling features
- Trains a classifier and exports prediction files

Current scope includes seasons `2010-11` through `2024-25`, plus a dynamically derived current season (for example, `2025-26`).

## Project Structure

- `src/data_collection.py`: data ingestion, rookie detection, ROY labeling, and raw/processed CSV creation
- `src/prepare_data.py`: feature engineering and creation of final training dataset
- `src/train_model.py`: model training, CV evaluation, model artifact export, and predictions export
- `data_raw/`: cached JSON responses from API endpoints
- `data_processed/`: generated CSV datasets for training
- `outputs/`: trained model artifact (`roy_model.pkl`)
- `predictions/`: prediction outputs (`roy_predictions_all_seasons.csv`, `predictions.csv`)

## Data Sources

Primary source: `nba_api` (stats.nba.com), notably:
- `LeagueDashPlayerStats`
- `PlayerAwards`

## Pipeline Workflow

1. Collect data
- Fetch season-level player stats (`leaguedash_{season}.json` cache)
- Detect rookies using:
- `SEASON_EXP == 0` when available, otherwise
- rookie-filtered league dash call (`leaguedash_rookies_{season}.json` cache)
- Label ROY using combined cache strategy:
- season cache first: `roy_winners_{season}.json`
- per-player awards cache second: `awards_{player_id}.json`
- targeted `PlayerAwards` fallback only when needed
- Output:
- `data_processed/raw_season_stats_all_seasons.csv`
- `data_processed/rookies_labeled.csv`

2. Prepare features
- Build per-75 production features with Bayesian smoothing
- Build efficiency and usage-related features (`TS`, `FG3_RATE`, `USG_RATE`, etc.)
- Output:
- `data_processed/roy_dataset.csv`

3. Train and predict
- Train baseline logistic regression pipeline
- Optionally train XGBoost if installed and select best by CV AUC
- Grouped CV by season (`GroupKFold`)
- Output:
- `outputs/roy_model.pkl`
- `predictions/roy_predictions_all_seasons.csv`
- `predictions/predictions.csv` (latest season, required two-column format)

## Quick Start

1. Install dependencies

```cmd
pip install -r requirements.txt
pip install -r requirements_extra.txt
```

2. Run pipeline

```cmd
python src\data_collection.py
python src\prepare_data.py
python src\train_model.py
```

## Notes

- API calls are heavily cached in `data_raw/` to speed up reruns.
- `predictions/predictions.csv` is generated from the latest available season in the dataset.
