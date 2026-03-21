"""
Train predictive models for ROY.

- Loads `data_processed/roy_dataset.csv`
- Trains Logistic Regression and XGBoost (if available)
- Evaluates with cross-validation and prints metrics
- Saves best model to `outputs/roy_model.pkl` and predictions to `predictions/`.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from data_collection import current_season

try:
    import xgboost as xgb
    HAS_XGB = True
except Exception:
    HAS_XGB = False

import joblib

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / 'data_processed'
OUTPUTS = ROOT / 'outputs'
PRED = ROOT / 'predictions'
OUTPUTS.mkdir(parents=True, exist_ok=True)
PRED.mkdir(parents=True, exist_ok=True)

# Minimum minutes threshold to reduce noise from low-sample players
MIN_THRESHOLD = 150
RACE_ODDS_TOLERANCE = 1e-3


def get_git_commit(root: Path) -> str:
    """Return current git commit hash if available."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return 'unknown'


def iso_utc_now() -> str:
    """Return current UTC timestamp in ISO-8601 `Z` format (seconds precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def build_run_id(run_timestamp_utc: str, git_commit: str) -> str:
    """Build traceable run identifier from UTC timestamp and short git commit."""
    ts_part = run_timestamp_utc.replace('-', '').replace(':', '').replace('T', '_').replace('Z', 'Z')
    short_commit = (git_commit[:7] if git_commit and git_commit != 'unknown' else 'unknown')
    return f'{ts_part}_{short_commit}'


def apply_per_season_race_odds(df_with_probs, prob_col='prob_roy_raw', out_col='race_odds'):
    """Normalize probabilities within each season so odds sum to 1."""
    df_normalized = df_with_probs.copy()
    df_normalized[out_col] = 0.0
    for season in df_normalized['SEASON'].unique():
        mask = df_normalized['SEASON'] == season
        season_probs = pd.to_numeric(df_normalized.loc[mask, prob_col], errors='coerce').fillna(0).clip(lower=0)
        total = float(season_probs.sum())
        if total > 0:
            df_normalized.loc[mask, out_col] = season_probs / total
        else:
            # Defensive fallback only for degenerate cases where all probs are zero.
            count = int(mask.sum())
            df_normalized.loc[mask, out_col] = (1.0 / count) if count > 0 else 0.0
    return df_normalized


def train():
    path = PROCESSED_DIR / 'roy_dataset.csv'
    if not path.exists():
        raise FileNotFoundError(f'{path} not found; run prepare_data.py first')

    df = pd.read_csv(path)
    
    # Filter training data: exclude current season (no ROY winner yet) and low-minute players
    curr_season = current_season()
    df_train = df[df['SEASON'] != curr_season].copy()  # Exclude current season
    df_train = df_train[df_train['MIN'] >= MIN_THRESHOLD].copy()  # Filter low minutes
    
    # Separate features for training
    X_train = df_train.drop(columns=['PLAYER_ID','PLAYER_NAME','SEASON','label'])
    y_train = df_train['label']
    groups_train = df_train['SEASON']  # For GroupKFold
    
    # All data for final predictions (including current season and low-minute players)
    X_all = df.drop(columns=['PLAYER_ID','PLAYER_NAME','SEASON','label'])
    
    # Create pipeline to prevent data leakage (scaler fit inside each CV fold)
    lr_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression(max_iter=2000, solver='saga', random_state=42))
    ])
    
    # Season-aware cross-validation (no leakage across seasons)
    cv = GroupKFold(n_splits=5)
    aucs = cross_val_score(lr_pipeline, X_train, y_train, groups=groups_train, cv=cv, scoring='roc_auc')
    print('LogisticRegression CV AUCs:', aucs, 'mean:', np.mean(aucs))
    print(f'Training on {len(df_train)} rookies (MIN >= {MIN_THRESHOLD}, known ROY only)')
    model_cv_results = {
        'logistic_regression': {
            'cv_auc_scores': aucs.tolist(),
            'cv_auc_mean': float(np.mean(aucs)),
            'cv_auc_std': float(np.std(aucs)),
        }
    }
    
    # Fit final model on all training data
    lr_pipeline.fit(X_train, y_train)

    best_model = lr_pipeline
    best_score = np.mean(aucs)
    model_name = 'logistic_regression'

    # Try XGBoost with class weighting for imbalanced data
    if HAS_XGB:
        print('Training XGBoost...')
        # Calculate scale_pos_weight for imbalanced classes (15 ROY winners vs ~800 non-winners)
        n_positives = (y_train == 1).sum()
        n_negatives = (y_train == 0).sum()
        scale_pos_weight = n_negatives / n_positives if n_positives > 0 else 1
        print(f'Using scale_pos_weight={scale_pos_weight:.2f} ({n_negatives} negatives / {n_positives} positives)')
        
        xgb_pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', xgb.XGBClassifier(
                eval_metric='logloss', 
                scale_pos_weight=scale_pos_weight,
                random_state=42
            ))
        ])
        aucs_x = cross_val_score(xgb_pipeline, X_train, y_train, groups=groups_train, cv=cv, scoring='roc_auc')
        print('XGBoost CV AUCs:', aucs_x, 'mean:', np.mean(aucs_x))
        model_cv_results['xgboost'] = {
            'cv_auc_scores': aucs_x.tolist(),
            'cv_auc_mean': float(np.mean(aucs_x)),
            'cv_auc_std': float(np.std(aucs_x)),
        }
        xgb_pipeline.fit(X_train, y_train)
        if np.mean(aucs_x) > best_score:
            best_model = xgb_pipeline
            best_score = np.mean(aucs_x)
            model_name = 'xgboost'

    run_timestamp_utc = iso_utc_now()
    git_commit = get_git_commit(ROOT)
    run_id = build_run_id(run_timestamp_utc, git_commit)

    out_path = OUTPUTS / 'roy_model.pkl'
    joblib.dump({'model': best_model, 'features': X_all.columns.tolist()}, out_path)
    print('Saved best model', model_name, 'to', out_path)

    # Generate predictions on ALL data (including current season and low-minute players)
    probs = best_model.predict_proba(X_all)[:,1]
    df_preds = df.drop(columns=['label']).copy()
    df_preds['prob_roy_raw'] = probs
    df_preds = apply_per_season_race_odds(df_preds, prob_col='prob_roy_raw', out_col='race_odds')
    df_preds['rank'] = (
        df_preds.groupby('SEASON')['race_odds']
        .rank(method='min', ascending=False)
        .astype(int)
    )
    df_preds['run_id'] = run_id
    df_preds['run_timestamp_utc'] = run_timestamp_utc
    df_preds['git_commit'] = git_commit
    
    # Sort by season and race odds.
    df_preds = df_preds.sort_values(['SEASON','race_odds'], ascending=[False, False])

    # Identify latest season rows.
    def season_start_year(season_str: str):
        if not isinstance(season_str, str):
            return -1
        parts = season_str.split('-')
        try:
            return int(parts[0])
        except Exception:
            import re
            m = re.search(r"(\d{4})", season_str)
            return int(m.group(1)) if m else -1

    df_preds['season_start'] = df_preds['SEASON'].apply(season_start_year)
    latest_start = df_preds['season_start'].max()
    latest_season_df = df_preds[df_preds['season_start'] == latest_start].copy()

    # Validate latest-season race odds before promoting outputs as latest.
    latest_odds_sum = float(latest_season_df['race_odds'].sum())
    odds_sum_check_passed = abs(latest_odds_sum - 1.0) <= RACE_ODDS_TOLERANCE
    if latest_season_df.empty:
        raise ValueError('No latest-season rows found; cannot export predictions.')
    if not odds_sum_check_passed:
        raise ValueError(
            f'Race odds sum check failed for latest season: sum={latest_odds_sum:.6f}, '
            f'tolerance={RACE_ODDS_TOLERANCE}.'
        )

    # Remove helper column before export.
    df_preds = df_preds.drop(columns=['season_start'])
    latest_season_df = latest_season_df.drop(columns=['season_start'])

    # Write latest-pointer exports.
    pred_path = PRED / 'roy_predictions_all_seasons.csv'
    df_preds.to_csv(pred_path, index=False)
    print('Saved predictions to', pred_path)

    latest_path = PRED / 'predictions.csv'
    latest_season_df = latest_season_df.sort_values('race_odds', ascending=False)
    latest_season_df.to_csv(latest_path, index=False)
    print('Saved latest-season predictions to', latest_path)

    # Backward-compatible two-column output for integrations that still expect it.
    two_col = latest_season_df[['PLAYER_NAME', 'race_odds']].rename(columns={'PLAYER_NAME': 'player_name', 'race_odds': 'probability'})
    two_col['probability'] = two_col['probability'].clip(0,1).round(6)
    two_col_path = PRED / 'predictions_two_col.csv'
    two_col.to_csv(two_col_path, index=False)
    print('Saved two-column predictions to', two_col_path)

    # Immutable per-run snapshot exports for trends/history.
    pred_history_dir = PRED / 'history' / run_id
    outputs_history_dir = OUTPUTS / 'history' / run_id
    pred_history_dir.mkdir(parents=True, exist_ok=True)
    outputs_history_dir.mkdir(parents=True, exist_ok=True)

    history_all_path = pred_history_dir / 'roy_predictions_all_seasons.csv'
    history_latest_path = pred_history_dir / 'predictions.csv'
    history_leaderboard_path = pred_history_dir / 'leaderboard_current_season.csv'
    history_two_col_path = pred_history_dir / 'predictions_two_col.csv'

    df_preds.to_csv(history_all_path, index=False)
    latest_season_df.to_csv(history_latest_path, index=False)
    latest_season_df.to_csv(history_leaderboard_path, index=False)
    two_col.to_csv(history_two_col_path, index=False)
    print('Saved prediction snapshots to', pred_history_dir)

    run_info = {
        'run_id': run_id,
        'run_timestamp_utc': run_timestamp_utc,
        'git_commit': git_commit,
        'current_season': curr_season,
        'seasons_in_dataset': sorted(df['SEASON'].dropna().astype(str).unique().tolist()),
        'seasons_in_training': sorted(df_train['SEASON'].dropna().astype(str).unique().tolist()),
        'min_threshold': MIN_THRESHOLD,
        'training_rows': int(len(df_train)),
        'training_positive_labels': int((y_train == 1).sum()),
        'training_negative_labels': int((y_train == 0).sum()),
        'selected_model': model_name,
        'selected_model_cv_auc_mean': float(best_score),
        'probability_presentation': 'season_normalized_race_odds',
        'latest_season_odds_sum': latest_odds_sum,
        'latest_season_odds_sum_tolerance': RACE_ODDS_TOLERANCE,
        'odds_sum_check_passed': odds_sum_check_passed,
        'model_cv': model_cv_results,
        'artifacts': {
            'model': str(out_path),
            'predictions_all_seasons': str(pred_path),
            'predictions_latest': str(latest_path),
            'predictions_latest_two_col': str(two_col_path),
            'predictions_history_dir': str(pred_history_dir),
        },
    }
    run_info_path = OUTPUTS / 'run_info.json'
    with open(run_info_path, 'w', encoding='utf-8') as f:
        json.dump(run_info, f, indent=2)
    print('Saved run metadata to', run_info_path)

    run_info_history_path = outputs_history_dir / 'run_info.json'
    with open(run_info_history_path, 'w', encoding='utf-8') as f:
        json.dump(run_info, f, indent=2)
    print('Saved run metadata snapshot to', run_info_history_path)


if __name__ == '__main__':
    train()
