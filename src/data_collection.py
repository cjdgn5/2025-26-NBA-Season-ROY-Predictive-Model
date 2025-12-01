"""
Data collection using nba_api.

This script fetches per-season player stats using `leaguedashplayerstats` and determines rookies
by checking each player's first season via `playercareerstats`. It also gathers ROY awards by
checking each player's awards via `playerawards` (if available) and creates a labeled CSV
for rookies across seasons.

Notes:
- Running this script will make many requests to the NBA stats endpoints; the script caches
  intermediate results to `data_raw/` to avoid re-querying.
- You may need to set `NBA_API_HEADERS` or have network access. The `nba_api` package
  handles headers automatically but occasionally requires a working network to reach stats.nba.com.
"""
from pathlib import Path
import time
import json
import logging
from typing import List

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats, playercareerstats, playerawards

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data_raw'
PROCESSED_DIR = ROOT / 'data_processed'
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('data_collection')

SEASONS = [
    '2010-11','2011-12','2012-13','2013-14','2014-15','2015-16','2016-17','2017-18',
    '2018-19','2019-20','2020-21','2021-22','2022-23','2023-24','2024-25'
]

# Caching helpers

def save_json(obj, path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def fetch_season_stats(season: str) -> pd.DataFrame:
    """Fetch season player statistics."""
    cache = RAW_DIR / f'leaguedash_{season}.json'
    if cache.exists():
        logger.info('Loading cached season stats for %s', season)
        data = load_json(cache)
        df = pd.DataFrame(data)
        return df

    logger.info('Fetching season stats for %s', season)
    res = leaguedashplayerstats.LeagueDashPlayerStats(season=season, season_type_all_star='Regular Season')
    df = res.get_data_frames()[0]
    save_json(df.to_dict(orient='records'), cache)
    time.sleep(1)
    return df


def normalize_season(season_str: str) -> str:
    """Normalize season strings so comparisons are reliable.
    Accepts formats like '2011-12' or '2011'. Converts '2011' -> '2011-12'.
    Leaves already hyphenated seasons unchanged.
    """
    if not season_str:
        return ''
    s = str(season_str).strip()
    if len(s) == 9 and s[4] == '-':
        return s
    if len(s) == 4 and s.isdigit():
        start = int(s)
        end = (start + 1) % 100
        return f"{start}-{str(end).zfill(2)}"
    return s


def player_first_season(player_id: int) -> str:
    """Determine player's rookie season using PlayerCareerStats.
    Uses the earliest unique season ID after sorting by start year.
    Cached result stored in data_raw/.
    """
    cache = RAW_DIR / f'career_{player_id}.json'
    if cache.exists():
        data = load_json(cache)
        return data.get('rookie_season')

    try:
        res = playercareerstats.PlayerCareerStats(player_id=player_id)
        df = res.get_data_frames()[0]
        seasons_list = [str(s) for s in df.get('SEASON_ID', [])]
        # Deduplicate and sort by numeric starting year
        unique = sorted(set(seasons_list), key=lambda s: int(str(s).split('-')[0])) if seasons_list else []
        rookie = unique[0] if unique else None
        save_json({'rookie_season': rookie, 'seasons': unique}, cache)
        time.sleep(0.6)
        return rookie
    except Exception as e:
        logger.warning('Failed to fetch career for %s: %s', player_id, e)
        return None


def player_has_roy(player_id: int, season: str) -> bool:
    """Check if a player has Rookie of the Year award in a given season using playerawards endpoint.
    Note: playerawards may return many awards; we look for 'Rookie of the Year'."""
    cache = RAW_DIR / f'awards_{player_id}.json'
    if cache.exists():
        data = load_json(cache)
        awards = data.get('awards', [])
    else:
        try:
            res = playerawards.PlayerAwards(player_id=player_id)
            df = res.get_data_frames()[0]
            awards = df.to_dict(orient='records')
            save_json({'awards': awards}, cache)
            time.sleep(0.6)
        except Exception as e:
            logger.warning('Failed to fetch awards for %s: %s', player_id, e)
            awards = []

    norm_target = normalize_season(season)
    for a in awards:
        name = a.get('AWARD_NAME') or a.get('AWARD') or ''
        season_award = a.get('SEASON') or a.get('SEASON_ID') or ''
        if 'Rookie of the Year' in str(name):
            if normalize_season(season_award) == norm_target:
                return True
    return False


def collect():
    rows = []
    for season in SEASONS:
        df = fetch_season_stats(season)
        # Normalize column names and select useful columns
        cols = [
            'PLAYER_ID','PLAYER_NAME','TEAM_ID','TEAM_ABBREVIATION','GP','W','L','MIN','FGM','FGA',
            'FG_PCT','FG3M','FG3A','FG3_PCT','FTM','FTA','FT_PCT','OREB','DREB','REB','AST','STL','BLK','TOV','PF','PTS'
        ]
        present_cols = [c for c in cols if c in df.columns]
        df_sub = df[present_cols].copy()
        df_sub['SEASON'] = season

        # Determine rookie flag by checking career first season
        for _, r in df_sub.iterrows():
            player_id = int(r['PLAYER_ID'])
            rookie_season = player_first_season(player_id)
            is_rookie = (rookie_season == season)
            rows.append({**r.to_dict(), 'ROOKIE': is_rookie})

    combined = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / 'raw_season_stats_all_seasons.csv'
    combined.to_csv(out_path, index=False)
    logger.info('Saved combined season stats to %s', out_path)

    # Filter rookies only and attempt to label ROY winners
    rookies = combined[combined['ROOKIE'] == True].copy()
    rookies['ROY'] = False
    for idx, r in rookies.iterrows():
        pid = int(r['PLAYER_ID'])
        season = r['SEASON']
        try:
            if player_has_roy(pid, season):
                rookies.at[idx, 'ROY'] = True
        except Exception:
            pass

    rookies_out = PROCESSED_DIR / 'rookies_labeled.csv'
    rookies.to_csv(rookies_out, index=False)
    logger.info('Saved rookies labeled to %s', rookies_out)


if __name__ == '__main__':
    collect()
