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
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score

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


def train():
    path = PROCESSED_DIR / 'roy_dataset.csv'
    if not path.exists():
        raise FileNotFoundError(f'{path} not found; run prepare_data.py first')

    df = pd.read_csv(path)
    X = df.drop(columns=['PLAYER_ID','PLAYER_NAME','SEASON','label'])
    y = df['label']

    # Simple baseline: logistic regression
    lr = LogisticRegression(max_iter=1000)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    aucs = cross_val_score(lr, X, y, cv=cv, scoring='roc_auc')
    print('LogisticRegression CV AUCs:', aucs, 'mean:', np.mean(aucs))
    lr.fit(X, y)

    best_model = lr
    best_score = np.mean(aucs)
    model_name = 'logistic_regression'

    # Try XGBoost
    if HAS_XGB:
        print('Training XGBoost...')
        xg = xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)
        aucs_x = cross_val_score(xg, X, y, cv=cv, scoring='roc_auc')
        print('XGBoost CV AUCs:', aucs_x, 'mean:', np.mean(aucs_x))
        xg.fit(X, y)
        if np.mean(aucs_x) > best_score:
            best_model = xg
            best_score = np.mean(aucs_x)
            model_name = 'xgboost'

    out_path = OUTPUTS / 'roy_model.pkl'
    joblib.dump({'model': best_model, 'features': X.columns.tolist()}, out_path)
    print('Saved best model', model_name, 'to', out_path)

    # Generate predictions (probabilities) and save ranking
    probs = best_model.predict_proba(X)[:,1]
    df_preds = df[['PLAYER_ID','PLAYER_NAME','SEASON']].copy()
    df_preds['prob_roy'] = probs
    df_preds = df_preds.sort_values(['SEASON','prob_roy'], ascending=[False, False])
    pred_path = PRED / 'roy_predictions_all_seasons.csv'
    df_preds.to_csv(pred_path, index=False)
    print('Saved predictions to', pred_path)


if __name__ == '__main__':
    train()
