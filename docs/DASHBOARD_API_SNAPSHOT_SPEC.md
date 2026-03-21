# Dashboard API & Snapshot Schema Draft

This document defines the pre-implementation API contract and storage layout for the ROY dashboard.

## Scope

- Consumer: non-technical viewers of the ROY race dashboard.
- Data source: pipeline outputs under `predictions/` and `outputs/`.
- Core guarantee: all displayed values must be traceable to one pipeline run.

## Run Identity

Every pipeline run should produce a unique `run_id` and UTC timestamp (`run_timestamp_utc`).

Recommended `run_id` format:
- `YYYYMMDD_HHMMSSZ_<short_commit>`
- Example: `20260321_143015Z_a1b2c3d`

## Canonical Fields

These fields are expected in API responses where applicable:

- `run_id`: string
- `run_timestamp_utc`: string (ISO 8601 UTC)
- `season`: string (e.g., `2025-26`)
- `player_id`: integer
- `player_name`: string
- `team`: string
- `position`: string or null
- `race_odds`: number (0-1, season-normalized)
- `prob_roy_raw`: number (0-1, non-normalized model output)
- `rank`: integer (1 = highest `race_odds`)
- `trend_direction`: enum(`up`,`down`,`flat`,`new`)
- `trend_delta`: number (current `race_odds` - previous run `race_odds`)

Player context fields:
- `pts_per_game`: number
- `reb_per_game`: number
- `ast_per_game`: number
- `ts`: number
- `usg_rate`: number
- `min_per_game`: number

Team/role context fields:
- `team_win_pct`: number
- `points_share`: number
- `minutes_share`: number

Optional display context:
- `draft_pick_log`: number
- `draft_tier_display`: string (derived for UI only)

## API Endpoints (v1)

### 1) GET `/api/v1/runs/latest`

Purpose:
- Return metadata for the latest completed pipeline run.

Response (200):

```json
{
  "run_id": "20260321_143015Z_a1b2c3d",
  "run_timestamp_utc": "2026-03-21T14:30:15Z",
  "season": "2025-26",
  "model_name": "xgboost",
  "probability_presentation": "season_normalized_race_odds",
  "record_count": 68,
  "odds_sum_current_season": 1.0000,
  "odds_sum_check_passed": true,
  "source_files": {
    "predictions": "predictions/history/20260321_143015Z_a1b2c3d/predictions.csv",
    "run_info": "outputs/history/20260321_143015Z_a1b2c3d/run_info.json"
  }
}
```

### 2) GET `/api/v1/leaderboard?season=2025-26&top_n=10`

Purpose:
- Primary dashboard table and top-10 visualization source.

Response (200):

```json
{
  "run_id": "20260321_143015Z_a1b2c3d",
  "run_timestamp_utc": "2026-03-21T14:30:15Z",
  "season": "2025-26",
  "top_n": 10,
  "odds_sum_current_season": 1.0000,
  "rows": [
    {
      "rank": 1,
      "player_id": 1641705,
      "player_name": "Player Name",
      "team": "DAL",
      "position": "G-F",
      "race_odds": 0.2123,
      "prob_roy_raw": 0.7812,
      "trend_direction": "up",
      "trend_delta": 0.0121,
      "pts_per_game": 19.4,
      "reb_per_game": 5.8,
      "ast_per_game": 4.2,
      "ts": 0.592,
      "usg_rate": 23.1,
      "min_per_game": 32.5,
      "team_win_pct": 0.588,
      "points_share": 0.118,
      "minutes_share": 0.102,
      "draft_pick_log": 1.386,
      "draft_tier_display": "Lottery"
    }
  ]
}
```

### 3) GET `/api/v1/player/{player_id}?season=2025-26`

Purpose:
- Player detail view and side-by-side context.

Response (200):

```json
{
  "run_id": "20260321_143015Z_a1b2c3d",
  "run_timestamp_utc": "2026-03-21T14:30:15Z",
  "season": "2025-26",
  "player": {
    "player_id": 1641705,
    "player_name": "Player Name",
    "team": "DAL",
    "position": "G-F",
    "rank": 1,
    "race_odds": 0.2123,
    "prob_roy_raw": 0.7812,
    "stats": {
      "pts_per_game": 19.4,
      "reb_per_game": 5.8,
      "ast_per_game": 4.2,
      "min_per_game": 32.5,
      "ts": 0.592,
      "usg_rate": 23.1,
      "team_win_pct": 0.588,
      "points_share": 0.118,
      "minutes_share": 0.102
    }
  },
  "rookie_comparison": {
    "field_ranks": {
      "pts_per_game_rank": 2,
      "min_per_game_rank": 3,
      "ts_rank": 6,
      "usg_rate_rank": 4,
      "team_win_pct_rank": 5
    }
  },
  "feature_contributions": null
}
```

Notes:
- `feature_contributions` remains `null` unless explicit explainability logic is added.

### 4) GET `/api/v1/trends?season=2025-26&player_id=1641705`

Purpose:
- Trend chart for one player across runs.

Response (200):

```json
{
  "season": "2025-26",
  "player_id": 1641705,
  "player_name": "Player Name",
  "series": [
    {
      "run_id": "20260314_120003Z_111aaaa",
      "run_timestamp_utc": "2026-03-14T12:00:03Z",
      "race_odds": 0.1842,
      "rank": 2
    },
    {
      "run_id": "20260321_143015Z_a1b2c3d",
      "run_timestamp_utc": "2026-03-21T14:30:15Z",
      "race_odds": 0.2123,
      "rank": 1
    }
  ]
}
```

### 5) GET `/api/v1/filters?season=2025-26`

Purpose:
- Populate dashboard filter controls.

Response (200):

```json
{
  "season": "2025-26",
  "teams": ["ATL", "BOS", "BRK"],
  "positions": ["C", "F", "F-C", "G", "G-F"],
  "draft_tiers": ["Top 3", "Lottery", "Mid First", "Late First", "Second Round", "Undrafted"]
}
```

## Error Response Shape

All non-2xx responses should follow:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "No predictions found for season 2027-28.",
    "details": null
  }
}
```

## Historical Snapshot Layout

Recommended structure:

```text
outputs/
  run_info.json
  history/
    <run_id>/
      run_info.json

predictions/
  predictions.csv
  roy_predictions_all_seasons.csv
  history/
    <run_id>/
      predictions.csv
      roy_predictions_all_seasons.csv
      leaderboard_current_season.csv
```

Where:
- `predictions/predictions.csv` is the latest-pointer file for UI/API defaults.
- `predictions/history/<run_id>/...` is immutable per run and used for trends/backtesting.
- `outputs/history/<run_id>/run_info.json` preserves run metadata for traceability.

## Data Contract Checks (Required)

At end of each pipeline run, verify:

1. Latest-season `race_odds` sum in tolerance (`abs(sum - 1.0) <= 0.001`).
2. No duplicate (`season`, `player_id`) rows in leaderboard source.
3. Required display fields exist and are non-null where expected.
4. `run_id` and `run_timestamp_utc` are attached to all exported prediction rows.

If any check fails, the run should be marked failed and not promoted as latest.

## Suggested Promotion Workflow

1. Pipeline writes candidate outputs to a staging location.
2. Validation checks run.
3. On success:
- copy files into `history/<run_id>/`
- update latest-pointer files (`predictions/predictions.csv`, etc.)
4. API serves latest run by default and can query by `run_id` for historical views.

## Dashboard Mapping

- Leaderboard table and top-10 bar chart -> `/api/v1/leaderboard`
- Trend arrows -> compare latest run vs previous run from history
- Player detail view -> `/api/v1/player/{player_id}`
- Trend line chart -> `/api/v1/trends`
- Filter controls -> `/api/v1/filters`

## Open Questions Before Build

1. Should latest run include only active rookies or all rookies with season rows?
2. Should ties in `race_odds` share rank or use deterministic secondary sort?
3. Should trend arrows compare against immediately previous run or previous run on same weekday (for weekly cadence)?
4. Do we expose `prob_roy_raw` to end users or keep it internal/API-only?
