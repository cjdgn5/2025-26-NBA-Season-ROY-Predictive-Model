Developer notes and how to run the ROY pipeline

1) Install dependencies (Windows cmd):

pip install -r requirements.txt
pip install -r requirements_extra.txt

2) Data collection (this can take several minutes due to many API requests):

python src\data_collection.py

This creates `data_processed/rookies_labeled.csv` and `data_processed/raw_season_stats_all_seasons.csv`.

3) Prepare dataset:

python src\prepare_data.py

This creates `data_processed/roy_dataset.csv`.

4) Train model and generate predictions:

python src\train_model.py

This saves best model to `outputs/roy_model.pkl` and predictions to `predictions/roy_predictions_all_seasons.csv`.

Notes and data sources:
- Primary source: `nba_api` (stats.nba.com). Key endpoints used: `LeagueDashPlayerStats`, `PlayerCareerStats`, and `PlayerAwards`.
- Scope: seasons 2010-11 through 2024-25 (configurable in `src/data_collection.py`).

Feature choices and justification are in `data_processed/README.md`.
