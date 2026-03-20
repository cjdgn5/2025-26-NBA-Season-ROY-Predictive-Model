"""
Prepare and engineer features for ROY prediction.

Reads `data_processed/rookies_labeled.csv`, computes per-75 possession stats, handles missing values,
and writes `data_processed/roy_dataset.csv` used for modeling.
"""
from pathlib import Path
from datetime import date
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / 'data_processed'
RAW_DIR = ROOT / 'data_raw'
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def per75(col, minutes, gp):
    # per 75 possessions = (total / minutes) * 75 ; if minutes==0, fallback to per game
    # 75 possessions approximates average team possessions in a 48-minute game
    with np.errstate(divide='ignore', invalid='ignore'):
        v = np.where(minutes>0, (col / minutes) * 75, col / np.where(gp>0, gp, 1))
    return v


def current_season() -> str:
    """Derive current NBA season string (e.g., '2025-26')."""
    today = date.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{str(end_year).zfill(2)}"


def run_preflight_checks(df: pd.DataFrame):
    """Validate rookie-labeled input before feature engineering."""
    required_cols = [
        'PLAYER_ID', 'PLAYER_NAME', 'SEASON', 'TEAM_ID', 'ROY', 'GP', 'MIN', 'W', 'L',
        'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV',
        'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT',
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f'Preflight failed: missing required columns: {missing}')

    dup_mask = df.duplicated(subset=['PLAYER_ID', 'SEASON'], keep=False)
    if dup_mask.any():
        dup_count = int(dup_mask.sum())
        raise ValueError(f'Preflight failed: found {dup_count} duplicate PLAYER_ID+SEASON rows.')

    roy_series = df['ROY']
    if roy_series.dtype == bool:
        roy_numeric = roy_series.astype(int)
    else:
        roy_numeric = roy_series.astype(str).str.strip().str.lower().map({'true': 1, 'false': 0})
        roy_numeric = roy_numeric.fillna(pd.to_numeric(roy_series, errors='coerce')).fillna(0).astype(int)

    current = current_season()
    completed = df[df['SEASON'].astype(str) != current].copy()
    completed['ROY_NUMERIC'] = roy_numeric.loc[completed.index]
    roy_by_season = completed.groupby('SEASON', dropna=False)['ROY_NUMERIC'].sum()
    bad = roy_by_season[roy_by_season != 1]
    if not bad.empty:
        details = ', '.join([f'{season}={int(count)}' for season, count in bad.items()])
        raise ValueError(
            'Preflight failed: completed seasons must each have exactly 1 ROY label. '
            f'Violations: {details}'
        )


def season_start_year(season_str: str) -> int:
    try:
        return int(str(season_str).split('-')[0])
    except Exception:
        return -1


def age_on_oct1(season_str: str, birthdate: str):
    if not birthdate:
        return np.nan
    birth = pd.to_datetime(birthdate, errors='coerce')
    if pd.isna(birth):
        return np.nan
    start_year = season_start_year(season_str)
    if start_year < 0:
        return np.nan
    ref = pd.Timestamp(year=start_year, month=10, day=1)
    return max((ref - birth).days / 365.25, 0)


def load_json_if_exists(path: Path):
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def prepare():
    path = PROCESSED_DIR / 'rookies_labeled.csv'
    if not path.exists():
        raise FileNotFoundError(f'{path} not found; run data_collection.py first')

    df = pd.read_csv(path)
    run_preflight_checks(df)

    # Basic cleaning
    df['PLAYER_ID'] = pd.to_numeric(df.get('PLAYER_ID', -1), errors='coerce').fillna(-1).astype(int)
    df['TEAM_ID'] = pd.to_numeric(df.get('TEAM_ID', -1), errors='coerce').fillna(-1).astype(int)
    df['MIN'] = pd.to_numeric(df.get('MIN', 0), errors='coerce').fillna(0)
    df['GP'] = pd.to_numeric(df.get('GP', 0), errors='coerce').fillna(0)
    gs_raw = df['GS'] if 'GS' in df.columns else pd.Series(0, index=df.index)
    df['GS'] = pd.to_numeric(gs_raw, errors='coerce').fillna(0)
    df['W'] = pd.to_numeric(df.get('W', 0), errors='coerce').fillna(0)
    df['L'] = pd.to_numeric(df.get('L', 0), errors='coerce').fillna(0)
    numeric_cols = ['PTS','REB','AST','STL','BLK','TOV','FGM','FGA','FG_PCT','FG3M','FG3A','FG3_PCT','FTM','FTA','FT_PCT']
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        else:
            df[c] = 0

    # Team success context
    df['TEAM_GAMES'] = df['W'] + df['L']
    df['TEAM_WIN_PCT'] = np.where(df['TEAM_GAMES'] > 0, df['W'] / df['TEAM_GAMES'], 0)
    df['GAMES_PLAYED_PCT'] = 0.0

    # Rookie role/share context: share of team production in season totals.
    raw_path = PROCESSED_DIR / 'raw_season_stats_all_seasons.csv'
    if not raw_path.exists():
        raise FileNotFoundError(f'{raw_path} not found; run data_collection.py first')
    raw_df = pd.read_csv(raw_path, usecols=['SEASON', 'TEAM_ID', 'MIN', 'PTS', 'GP'])
    raw_df['TEAM_ID'] = pd.to_numeric(raw_df.get('TEAM_ID', -1), errors='coerce').fillna(-1).astype(int)
    raw_df['MIN'] = pd.to_numeric(raw_df.get('MIN', 0), errors='coerce').fillna(0)
    raw_df['PTS'] = pd.to_numeric(raw_df.get('PTS', 0), errors='coerce').fillna(0)
    raw_df['GP'] = pd.to_numeric(raw_df.get('GP', 0), errors='coerce').fillna(0)
    team_totals = (
        raw_df.groupby(['SEASON', 'TEAM_ID'], as_index=False)[['MIN', 'PTS']]
        .sum()
        .rename(columns={'MIN': 'TEAM_TOTAL_MIN', 'PTS': 'TEAM_TOTAL_PTS'})
    )
    df = df.merge(team_totals, on=['SEASON', 'TEAM_ID'], how='left')
    df['TEAM_TOTAL_MIN'] = pd.to_numeric(df['TEAM_TOTAL_MIN'], errors='coerce').fillna(0)
    df['TEAM_TOTAL_PTS'] = pd.to_numeric(df['TEAM_TOTAL_PTS'], errors='coerce').fillna(0)
    df['MINUTES_SHARE'] = np.where(df['TEAM_TOTAL_MIN'] > 0, df['MIN'] / df['TEAM_TOTAL_MIN'], 0)
    df['POINTS_SHARE'] = np.where(df['TEAM_TOTAL_PTS'] > 0, df['PTS'] / df['TEAM_TOTAL_PTS'], 0)

    # Availability/stability context normalized by season length.
    season_max_games = raw_df.groupby('SEASON', as_index=False)['GP'].max().rename(columns={'GP': 'SEASON_MAX_GP'})
    df = df.merge(season_max_games, on='SEASON', how='left')
    df['SEASON_MAX_GP'] = pd.to_numeric(df['SEASON_MAX_GP'], errors='coerce').fillna(82)
    df['GAMES_PLAYED_PCT'] = np.where(df['SEASON_MAX_GP'] > 0, df['GP'] / df['SEASON_MAX_GP'], 0)
    df['GAMES_PLAYED_PCT'] = df['GAMES_PLAYED_PCT'].clip(lower=0, upper=1)

    # Real production volume features.
    df['TOTAL_POINTS'] = df['PTS']
    df['TOTAL_MINUTES'] = df['MIN']
    df['PTS_per_game'] = np.where(df['GP'] > 0, df['PTS'] / df['GP'], 0)
    df['REB_per_game'] = np.where(df['GP'] > 0, df['REB'] / df['GP'], 0)
    df['AST_per_game'] = np.where(df['GP'] > 0, df['AST'] / df['GP'], 0)
    df['STARTS'] = df['GS'].clip(lower=0)
    df['START_PCT'] = np.where(df['GP'] > 0, df['STARTS'] / df['GP'], 0)
    df['START_PCT'] = df['START_PCT'].clip(lower=0, upper=1)

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
    
    # Calculate simplified Usage Rate (USG% proxy):
    # percentage of usage actions per minute over the season.
    df['USG_RATE'] = np.where(
        df['MIN'] > 0,
        100 * (df['FGA'] + 0.44*df['FTA'] + df['TOV']) / df['MIN'],
        0
    )

    # Draft and age context from cached player info.
    player_ids = sorted(set(df['PLAYER_ID'].tolist()))
    player_info = {}
    for pid in player_ids:
        info = load_json_if_exists(RAW_DIR / f'info_{pid}.json') or {}
        player_info[pid] = {
            'draft_pick': info.get('draft_pick'),
            'draft_round': info.get('draft_round'),
            'birthdate': info.get('birthdate'),
        }
    df['DRAFT_PICK_RAW'] = df['PLAYER_ID'].map(lambda pid: player_info.get(pid, {}).get('draft_pick'))
    df['DRAFT_ROUND_RAW'] = df['PLAYER_ID'].map(lambda pid: player_info.get(pid, {}).get('draft_round'))
    df['IS_UNDRAFTED'] = df['DRAFT_PICK_RAW'].isna().astype(int)
    df['DRAFT_PICK'] = pd.to_numeric(df['DRAFT_PICK_RAW'], errors='coerce').fillna(61)
    df['DRAFT_ROUND'] = pd.to_numeric(df['DRAFT_ROUND_RAW'], errors='coerce')
    df['DRAFT_ROUND'] = np.where(
        df['DRAFT_ROUND'].notna(),
        df['DRAFT_ROUND'],
        np.where(df['DRAFT_PICK'] <= 30, 1, np.where(df['DRAFT_PICK'] <= 60, 2, 3))
    )
    df['AGE_OCT1'] = [
        age_on_oct1(season, player_info.get(pid, {}).get('birthdate'))
        for pid, season in zip(df['PLAYER_ID'], df['SEASON'])
    ]
    df['AGE_OCT1'] = pd.to_numeric(df['AGE_OCT1'], errors='coerce')
    if df['AGE_OCT1'].notna().any():
        df['AGE_OCT1'] = df['AGE_OCT1'].fillna(df['AGE_OCT1'].median())
    else:
        df['AGE_OCT1'] = df['AGE_OCT1'].fillna(20.0)

    # Draft normalization features for improved scale handling.
    df['DRAFT_PICK_LOG'] = np.log1p(df['DRAFT_PICK'])
    df['DRAFT_TIER'] = np.where(
        df['IS_UNDRAFTED'] == 1,
        4,
        np.where(df['DRAFT_PICK'] <= 14, 1, np.where(df['DRAFT_PICK'] <= 30, 2, 3))
    )

    # Rookie-relative rank features within each season.
    df['PTS_rank_rookies'] = df.groupby('SEASON')['PTS_per_game'].rank(method='min', ascending=False)
    df['MIN_rank_rookies'] = df.groupby('SEASON')['TOTAL_MINUTES'].rank(method='min', ascending=False)
    df['TS_rank_rookies'] = df.groupby('SEASON')['TS'].rank(method='min', ascending=False)
    df['TEAM_WIN_PCT_rank_rookies'] = df.groupby('SEASON')['TEAM_WIN_PCT'].rank(method='min', ascending=False)

    features = [
        'GP','MIN',
        'STARTS','START_PCT',
        'TEAM_GAMES','TEAM_WIN_PCT','GAMES_PLAYED_PCT',
        'MINUTES_SHARE','POINTS_SHARE',
        'TOTAL_POINTS','TOTAL_MINUTES',
        'PTS_per_game','REB_per_game','AST_per_game',
        'MIN_per_game',
        'PTS_per75',
        'REB_per75',
        'AST_per75',
        'STL_per75',
        'BLK_per75',
        'TS','FG_PCT',
        'FG3_RATE',
        'FT_PCT',
        'TOV','USG_RATE',
        'PTS_rank_rookies','MIN_rank_rookies','TS_rank_rookies','TEAM_WIN_PCT_rank_rookies',
        'DRAFT_PICK_LOG','DRAFT_TIER','DRAFT_ROUND','IS_UNDRAFTED','AGE_OCT1'
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
