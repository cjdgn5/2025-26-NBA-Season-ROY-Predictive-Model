"""
Prepare and engineer features for ROY prediction.

Reads `data_processed/rookies_labeled.csv`, computes per-75 possession stats, handles missing values,
and writes `data_processed/roy_dataset.csv` used for modeling.
"""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / 'data_processed'
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def per75(col, minutes, gp):
    # per 75 possessions = (total / minutes) * 75 ; if minutes==0, fallback to per game
    # 75 possessions approximates average team possessions in a 48-minute game
    with np.errstate(divide='ignore', invalid='ignore'):
        v = np.where(minutes>0, (col / minutes) * 75, col / np.where(gp>0, gp, 1))
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

    # Compute per-75 possession features (better accounts for pace than per-36)
    raw_pts75 = per75(df['PTS'], df['MIN'], df['GP'])
    raw_reb75 = per75(df['REB'], df['MIN'], df['GP'])
    raw_ast75 = per75(df['AST'], df['MIN'], df['GP'])
    raw_stl75 = per75(df['STL'], df['MIN'], df['GP'])
    raw_blk75 = per75(df['BLK'], df['MIN'], df['GP'])
    
    # Apply Bayesian smoothing: shrink low-minute per-75 toward league mean
    # weight = MIN / (MIN + prior_weight); smoothed = weight*raw + (1-weight)*prior_mean
    prior_weight = 300  # equivalent to ~8-10 games of starter minutes
    prior_pts = raw_pts75.mean()
    prior_reb = raw_reb75.mean()
    prior_ast = raw_ast75.mean()
    prior_stl = raw_stl75.mean()
    prior_blk = raw_blk75.mean()
    
    df['PTS_per75'] = (df['MIN']*raw_pts75 + prior_weight*prior_pts) / (df['MIN'] + prior_weight)
    df['REB_per75'] = (df['MIN']*raw_reb75 + prior_weight*prior_reb) / (df['MIN'] + prior_weight)
    df['AST_per75'] = (df['MIN']*raw_ast75 + prior_weight*prior_ast) / (df['MIN'] + prior_weight)
    df['STL_per75'] = (df['MIN']*raw_stl75 + prior_weight*prior_stl) / (df['MIN'] + prior_weight)
    df['BLK_per75'] = (df['MIN']*raw_blk75 + prior_weight*prior_blk) / (df['MIN'] + prior_weight)

    # Shooting efficiency features
    df['TS'] = df['PTS'] / (2*(df['FGA'] + 0.44*df['FTA']) + 1e-6)
    df['FG3_RATE'] = np.where(df['FGA']>0, df['FG3A']/df['FGA'], 0)
    
    # Add minutes per game (playing time trust indicator)
    df['MIN_per_game'] = np.where(df['GP']>0, df['MIN']/df['GP'], 0)
    
    # Calculate Usage Rate (USG%): percentage of team plays used by player while on court
    # Simplified as per-75 possession usage actions
    df['USG_RATE'] = np.where(
        df['MIN'] > 0,
        100 * (df['FGA'] + 0.44*df['FTA'] + df['TOV']) / (df['MIN'] / 75),  # per-75 usage actions
        0
    )

    features = [
        'GP','MIN',
        'MIN_per_game',
        'PTS_per75',
        'REB_per75',
        'AST_per75',
        'STL_per75',
        'BLK_per75',
        'TS','FG_PCT',
        'FG3_RATE',
        'FT_PCT',
        'TOV','USG_RATE'
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
