"""
Prepare and engineer features for ROY prediction.

Reads `data_processed/rookies_labeled.csv`, computes per-36 stats, handles missing values,
and writes `data_processed/roy_dataset.csv` used for modeling.
"""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / 'data_processed'
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def per36(col, minutes, gp):
    # per 36 = (total / minutes) * 36 ; if minutes==0, fallback to per game
    with np.errstate(divide='ignore', invalid='ignore'):
        v = np.where(minutes>0, (col / minutes) * 36, col / np.where(gp>0, gp, 1))
    return v


def prepare():
    path = PROCESSED_DIR / 'rookies_labeled.csv'
    if not path.exists():
        raise FileNotFoundError(f'{path} not found; run data_collection.py first')

    df = pd.read_csv(path)

    # Basic cleaning
    df['MIN'] = pd.to_numeric(df.get('MIN', 0), errors='coerce').fillna(0)
    df['GP'] = pd.to_numeric(df.get('GP', 0), errors='coerce').fillna(0)
    numeric_cols = ['PTS','REB','AST','STL','BLK','TOV','FGM','FGA','FG_PCT','FG3M','FG3A','FG3_PCT','FTM','FTA','FT_PCT']
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        else:
            df[c] = 0

    # Compute per-36 features
    df['PTS_per36'] = per36(df['PTS'], df['MIN'], df['GP'])
    df['REB_per36'] = per36(df['REB'], df['MIN'], df['GP'])
    df['AST_per36'] = per36(df['AST'], df['MIN'], df['GP'])
    df['STL_per36'] = per36(df['STL'], df['MIN'], df['GP'])
    df['BLK_per36'] = per36(df['BLK'], df['MIN'], df['GP'])

    # Shooting efficiency features
    df['TS'] = df['PTS'] / (2*(df['FGA'] + 0.44*df['FTA']) + 1e-6)
    df['FG3_RATE'] = np.where(df['FGA']>0, df['FG3A']/df['FGA'], 0)

    features = [
        'GP','MIN','PTS_per36','REB_per36','AST_per36','STL_per36','BLK_per36',
        'TS','FG_PCT','FG3_RATE','FT_PCT','TOV'
    ]

    # Keep label
    df['label'] = df['ROY'].astype(int)

    out_cols = ['PLAYER_ID','PLAYER_NAME','SEASON'] + features + ['label']
    final = df[out_cols].copy()

    out_path = PROCESSED_DIR / 'roy_dataset.csv'
    final.to_csv(out_path, index=False)
    print('Saved prepared dataset to', out_path)


if __name__ == '__main__':
    prepare()
