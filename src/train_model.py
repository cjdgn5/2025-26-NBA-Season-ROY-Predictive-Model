"""
Train predictive models for ROY.

- Loads `data_processed/roy_dataset.csv`
- Trains Logistic Regression and XGBoost (if available)
- Evaluates with cross-validation and prints metrics
- Saves best model to `outputs/roy_model.pkl` and predictions to `predictions/`.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from scipy.special import softmax
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

def apply_per_season_softmax(df_with_probs, prob_col='prob_roy'):
    """Apply softmax normalization within each season so probabilities sum to 1."""
    df_normalized = df_with_probs.copy()
    for season in df_normalized['SEASON'].unique():
        mask = df_normalized['SEASON'] == season
        season_probs = df_normalized.loc[mask, prob_col].values
        normalized_probs = softmax(season_probs)
        df_normalized.loc[mask, prob_col] = normalized_probs
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
        xgb_pipeline.fit(X_train, y_train)
        if np.mean(aucs_x) > best_score:
            best_model = xgb_pipeline
            best_score = np.mean(aucs_x)
            model_name = 'xgboost'

    out_path = OUTPUTS / 'roy_model.pkl'
    joblib.dump({'model': best_model, 'features': X_all.columns.tolist()}, out_path)
    print('Saved best model', model_name, 'to', out_path)

    # Generate predictions on ALL data (including current season and low-minute players)
    probs = best_model.predict_proba(X_all)[:,1]
    df_preds = df[['PLAYER_ID','PLAYER_NAME','SEASON']].copy()
    df_preds['prob_roy'] = probs
    
    # Sort by season and probability (no softmax normalization to preserve model's confidence spread)
    df_preds = df_preds.sort_values(['SEASON','prob_roy'], ascending=[False, False])
    pred_path = PRED / 'roy_predictions_all_seasons.csv'
    df_preds.to_csv(pred_path, index=False)
    print('Saved predictions to', pred_path)

    # Produce the required two-column `predictions.csv` for the latest season
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
    two_col = latest_season_df[['PLAYER_NAME', 'prob_roy']].rename(columns={'PLAYER_NAME': 'player_name', 'prob_roy': 'probability'})
    two_col['probability'] = two_col['probability'].clip(0,1).round(6)
    two_col_path = PRED / 'predictions.csv'
    two_col.to_csv(two_col_path, index=False)
    print('Saved two-column predictions to', two_col_path)


if __name__ == '__main__':
    train()
