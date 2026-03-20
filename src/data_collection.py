"""
Data collection using nba_api.

This script fetches per-season player stats using `leaguedashplayerstats` and determines rookies
using season-level rookie filtering (`player_experience`/`SEASON_EXP`). It also gathers ROY awards
by checking each player's awards via `playerawards` (if available) and creates a labeled CSV
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
import argparse
from typing import Set

import pandas as pd
from datetime import date
from nba_api.stats.endpoints import leaguedashplayerstats, playerawards, commonplayerinfo

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data_raw'
PROCESSED_DIR = ROOT / 'data_processed'
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('data_collection')
MAX_API_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5
PROGRESS_LOG_EVERY = 25

def current_season() -> str:
    """Derive the current NBA season string like '2025-26'. Assumes season start Aug/Sept."""
    today = date.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{str(end_year).zfill(2)}"

BASE_SEASONS = [
    '2010-11','2011-12','2012-13','2013-14','2014-15','2015-16','2016-17','2017-18',
    '2018-19','2019-20','2020-21','2021-22','2022-23','2023-24','2024-25'
]
SEASONS = sorted(set(BASE_SEASONS + [current_season()]))

# Caching helpers

def save_json(obj, path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def to_int_set(values) -> Set[int]:
    """Safely coerce iterable values to an int set, dropping nulls."""
    series = pd.Series(values, dtype='object')
    numeric = pd.to_numeric(series, errors='coerce').dropna().astype(int)
    return set(numeric.tolist())


def run_with_retries(callable_fn, operation_label: str):
    """Execute API calls with bounded retries and exponential backoff."""
    last_error = None
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            return callable_fn()
        except Exception as e:
            last_error = e
            if attempt < MAX_API_RETRIES:
                wait_seconds = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    'Attempt %d/%d failed for %s: %s. Retrying in %.1fs',
                    attempt, MAX_API_RETRIES, operation_label, e, wait_seconds
                )
                time.sleep(wait_seconds)
            else:
                logger.warning(
                    'All %d attempts failed for %s: %s',
                    MAX_API_RETRIES, operation_label, e
                )
    raise last_error


def fetch_season_stats(season: str, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch season player statistics."""
    cache = RAW_DIR / f'leaguedash_{season}.json'
    if force_refresh and cache.exists():
        logger.info('Refreshing season stats cache for %s', season)
        cache.unlink()
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


def fetch_rookie_player_ids(season: str, force_refresh: bool = False) -> Set[int]:
    """Fetch rookie player IDs for a season in one request.

    Uses LeagueDashPlayerStats with a rookie experience filter and caches results.
    """
    cache = RAW_DIR / f'leaguedash_rookies_{season}.json'
    if force_refresh and cache.exists():
        logger.info('Refreshing rookie list cache for %s', season)
        cache.unlink()
    if cache.exists():
        data = load_json(cache)
        return to_int_set([r.get('PLAYER_ID') for r in data if isinstance(r, dict)])

    logger.info('Fetching rookie player list for %s', season)
    errors = []
    attempts = [
        {'player_experience_nullable': 'Rookie'},
        {'player_experience': 'Rookie'},
    ]

    for extra_kwargs in attempts:
        try:
            res = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star='Regular Season',
                **extra_kwargs,
            )
            df = res.get_data_frames()[0]
            records = df.to_dict(orient='records')
            save_json(records, cache)
            time.sleep(0.6)
            return to_int_set(df.get('PLAYER_ID', []))
        except TypeError as e:
            errors.append(str(e))
            continue
        except Exception as e:
            errors.append(str(e))
            continue

    logger.warning('Failed rookie list fetch for %s; returning empty set. Errors: %s', season, errors)
    return set()


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


def player_has_roy(player_id: int, season: str) -> bool:
    """Check if a player has Rookie of the Year award in a given season using playerawards endpoint.
    Note: playerawards may return many awards; we look for 'Rookie of the Year'."""
    cache = RAW_DIR / f'awards_{player_id}.json'
    if cache.exists():
        data = load_json(cache)
        awards = data.get('awards', [])
    else:
        try:
            df = run_with_retries(
                lambda: playerawards.PlayerAwards(player_id=player_id).get_data_frames()[0],
                f'PlayerAwards for player_id={player_id}'
            )
            awards = df.to_dict(orient='records')
            save_json({'awards': awards}, cache)
            time.sleep(0.6)
        except Exception as e:
            logger.warning('Failed to fetch awards for %s: %s', player_id, e)
            awards = []

    norm_target = normalize_season(season)
    for a in awards:
        # Check DESCRIPTION field (primary), then AWARD_NAME, then AWARD as fallbacks
        name = a.get('DESCRIPTION') or a.get('AWARD_NAME') or a.get('AWARD') or ''
        season_award = a.get('SEASON') or a.get('SEASON_ID') or ''
        if 'Rookie of the Year' in str(name):
            if normalize_season(season_award) == norm_target:
                return True
    return False


def fetch_player_info_cached(player_id: int) -> dict:
    """Load or fetch player bio info used for feature engineering."""
    cache = RAW_DIR / f'info_{player_id}.json'
    if cache.exists():
        return load_json(cache)

    info = {'draft_pick': None, 'draft_round': None, 'birthdate': None}
    try:
        df = run_with_retries(
            lambda: commonplayerinfo.CommonPlayerInfo(player_id=player_id).get_data_frames()[0],
            f'CommonPlayerInfo for player_id={player_id}'
        )
        if not df.empty:
            row = df.iloc[0].to_dict()
            draft_number = row.get('DRAFT_NUMBER')
            draft_round = row.get('DRAFT_ROUND')
            birthdate = row.get('BIRTHDATE')

            try:
                info['draft_pick'] = int(draft_number) if str(draft_number).isdigit() else None
            except Exception:
                info['draft_pick'] = None

            try:
                info['draft_round'] = int(draft_round) if str(draft_round).isdigit() else None
            except Exception:
                info['draft_round'] = None

            info['birthdate'] = str(birthdate) if birthdate not in [None, ''] else None
        save_json(info, cache)
        time.sleep(0.6)
    except Exception as e:
        logger.warning('Failed to fetch player info for %s: %s', player_id, e)
        save_json(info, cache)
    return info


def get_or_build_season_roy_winners(season: str, rookie_player_ids: Set[int]) -> Set[int]:
    """Return ROY winner IDs for a season with a season-level cache.

    Strategy:
    1) Use `roy_winners_{season}.json` if available.
    2) Otherwise scan existing per-player `awards_{player_id}.json` caches for rookies.
    3) If still unresolved and season is not current, fallback to targeted player award fetches.
    """
    cache = RAW_DIR / f'roy_winners_{season}.json'
    if cache.exists():
        data = load_json(cache)
        winners = to_int_set(data.get('winner_player_ids', []))
        logger.info('Loaded season ROY cache for %s (%d winner ids)', season, len(winners))
        return winners

    winners = set()
    missing_awards_cache = []
    target_season = normalize_season(season)

    for pid in sorted(rookie_player_ids):
        awards_cache = RAW_DIR / f'awards_{pid}.json'
        if not awards_cache.exists():
            missing_awards_cache.append(pid)
            continue

        data = load_json(awards_cache)
        awards = data.get('awards', [])
        for award in awards:
            name = award.get('DESCRIPTION') or award.get('AWARD_NAME') or award.get('AWARD') or ''
            season_award = award.get('SEASON') or award.get('SEASON_ID') or ''
            if 'Rookie of the Year' in str(name) and normalize_season(season_award) == target_season:
                winners.add(int(pid))
                break
        if winners:
            break

    # Fallback: targeted fetches only if season cache could not be resolved from existing player caches.
    if not winners and target_season != normalize_season(current_season()):
        total_missing = len(missing_awards_cache)
        for idx, pid in enumerate(missing_awards_cache, start=1):
            if player_has_roy(pid, season):
                winners.add(int(pid))
                break
            if idx % PROGRESS_LOG_EVERY == 0 or idx == total_missing:
                logger.info(
                    'Awards fallback fetch progress for %s: %d/%d',
                    season, idx, total_missing
                )

    save_json(
        {
            'season': season,
            'winner_player_ids': sorted(winners),
            'rookie_player_count': len(rookie_player_ids),
            'missing_awards_cache_count': len(missing_awards_cache),
        },
        cache,
    )
    logger.info('Built season ROY cache for %s (%d winner ids)', season, len(winners))
    return winners


def collect(refresh_current_season_stats: bool = True, refresh_all_season_stats: bool = False):
    rows = []
    curr = current_season()
    for season in SEASONS:
        force_refresh = refresh_all_season_stats or (refresh_current_season_stats and season == curr)
        df = fetch_season_stats(season, force_refresh=force_refresh)
        if 'SEASON_EXP' in df.columns:
            rookie_mask = pd.to_numeric(df['SEASON_EXP'], errors='coerce').fillna(-1).astype(int) == 0
            rookie_ids = set(pd.to_numeric(df.loc[rookie_mask, 'PLAYER_ID'], errors='coerce').dropna().astype(int))
            logger.info('Using SEASON_EXP for rookie detection in %s (%d rookies)', season, len(rookie_ids))
        else:
            rookie_ids = fetch_rookie_player_ids(season, force_refresh=force_refresh)
            logger.info('Using rookie-filtered endpoint for %s (%d rookies)', season, len(rookie_ids))

        # Normalize column names and select useful columns
        cols = [
            'PLAYER_ID','PLAYER_NAME','TEAM_ID','TEAM_ABBREVIATION','GP','GS','W','L','MIN','FGM','FGA',
            'FG_PCT','FG3M','FG3A','FG3_PCT','FTM','FTA','FT_PCT','OREB','DREB','REB','AST','STL','BLK','TOV','PF','PTS'
        ]
        present_cols = [c for c in cols if c in df.columns]
        df_sub = df[present_cols].copy()
        df_sub['SEASON'] = season
        df_sub['ROOKIE'] = pd.to_numeric(df_sub['PLAYER_ID'], errors='coerce').fillna(-1).astype(int).isin(rookie_ids)
        rows.extend(df_sub.to_dict(orient='records'))

    combined = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / 'raw_season_stats_all_seasons.csv'
    combined.to_csv(out_path, index=False)
    logger.info('Saved combined season stats to %s', out_path)

    # Filter rookies only and attempt to label ROY winners
    rookies = combined[combined['ROOKIE'] == True].copy()
    rookies['ROY'] = False
    rookie_ids_numeric = pd.to_numeric(rookies['PLAYER_ID'], errors='coerce').fillna(-1).astype(int)
    rookies['PLAYER_ID'] = rookie_ids_numeric
    unique_rookie_ids = sorted(set(rookie_ids_numeric.tolist()))
    total_rookies = len(unique_rookie_ids)
    for idx, pid in enumerate(unique_rookie_ids, start=1):
        fetch_player_info_cached(int(pid))
        if idx % PROGRESS_LOG_EVERY == 0 or idx == total_rookies:
            logger.info(
                'Player info cache progress: %d/%d rookies',
                idx, total_rookies
            )

    for season, season_df in rookies.groupby('SEASON'):
        season_rookie_ids = set(pd.to_numeric(season_df['PLAYER_ID'], errors='coerce').dropna().astype(int))
        winners = get_or_build_season_roy_winners(season, season_rookie_ids)
        logger.info('Applying ROY labels for %s (rookies=%d, winners=%d)', season, len(season_rookie_ids), len(winners))
        mask = rookies['SEASON'] == season
        rookies.loc[mask, 'ROY'] = rookies.loc[mask, 'PLAYER_ID'].isin(winners)

    rookies_out = PROCESSED_DIR / 'rookies_labeled.csv'
    rookies.to_csv(rookies_out, index=False)
    logger.info('Saved rookies labeled to %s', rookies_out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Collect and label ROY rookie data.')
    parser.add_argument(
        '--refresh-current-season-stats',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Refresh cached season stats and rookie list for current season (default: true).',
    )
    parser.add_argument(
        '--refresh-all-season-stats',
        action='store_true',
        help='Refresh cached season stats and rookie lists for all seasons.',
    )
    args = parser.parse_args()
    collect(
        refresh_current_season_stats=args.refresh_current_season_stats,
        refresh_all_season_stats=args.refresh_all_season_stats,
    )
