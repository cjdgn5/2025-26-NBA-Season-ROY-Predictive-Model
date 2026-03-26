# README_DEV

Developer-oriented runbook for the ROY pipeline.

## Setup (Windows CMD)

```cmd
pip install -r requirements.txt
pip install -r requirements_extra.txt
```

## Standard Pipeline Run

```cmd
python src\data_collection.py
python src\prepare_data.py
python src\train_model.py
```

## What Each Step Produces

1. `python src\data_collection.py`
- `data_processed/raw_season_stats_all_seasons.csv`
- `data_processed/rookies_labeled.csv`

2. `python src\prepare_data.py`
- Runs preflight checks (required columns, duplicates, ROY-label sanity)
- `data_processed/roy_dataset.csv`

3. `python src\train_model.py`
- `outputs/roy_model.pkl`
- `outputs/run_info.json`
- `outputs/history/<run_id>/run_info.json`
- `predictions/roy_predictions_all_seasons.csv`
- `predictions/predictions.csv` (latest season, rich fields + run traceability)
- `predictions/predictions_two_col.csv` (legacy 2-column format)
- `predictions/history/<run_id>/...` (immutable per-run snapshots)

## Refresh Options

Refresh current season:

```cmd
python src\data_collection.py --refresh-current-season-stats
```

Refresh all seasons:

```cmd
python src\data_collection.py --refresh-all-season-stats
```

## Current Modeling Notes

- Prediction presentation uses season-normalized race odds.
- Raw model probability is still saved (`prob_roy_raw`) for analysis.
- `run_id` and `run_timestamp_utc` are attached to prediction exports for traceability.
- Final UI-facing output should use `predictions/predictions.csv`.

## Troubleshooting

- If API calls timeout, rerun collection; cache + retry/backoff should recover most failures.
- If `prepare_data.py` fails preflight, fix the input issue before training.
- If `nba_api` import fails, confirm the active interpreter is `.venv` and reinstall requirements.

## Related Docs

- `README.md` for high-level project overview
- `data_processed/README.md` for dataset-level notes

## API Service (Read-Only, v1)

Run locally (from repo root):

```cmd
python -m uvicorn src.api_service:app --host 127.0.0.1 --port 8000 --reload
```

Primary endpoints:
- `GET /api/v1/runs/latest`
- `GET /api/v1/leaderboard?season=2025-26&top_n=10`
- `GET /api/v1/player/{player_id}?season=2025-26`
- `GET /api/v1/trends?season=2025-26&player_id={player_id}`
- `GET /api/v1/filters?season=2025-26`
- `GET /health/live`
- `GET /health/ready`
