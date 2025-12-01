This folder contains processed datasets for the ROY model pipeline.

Files:
- `raw_season_stats_all_seasons.csv`: combined per-season player stats for seasons collected.
- `rookies_labeled.csv`: subset of the above filtered to rookies with a `ROY` boolean label where available.
- `roy_dataset.csv`: final modeling dataset with engineered features and `label` column (1=ROY, 0=not).

Data sources and notes:
- Primary data source: `nba_api` (stats.nba.com endpoints such as `leaguedashplayerstats`, `playercareerstats`, and `playerawards`).
- Scope: seasons from 2010-11 through 2024-25. This range provides a balance between historical depth and relevance to modern playstyles.

Feature choices and justification:
- Per-36 performance metrics (`PTS_per36`, `REB_per36`, `AST_per36`, `STL_per36`, `BLK_per36`): normalize workload differences and focus on per-minute production.
- Shooting efficiency (`TS`, `FG_PCT`, `FG3_RATE`, `FT_PCT`): efficiency often distinguishes award-caliber rookies.
- Volume measures (`GP`, `MIN`): playing time availability is important for accumulating counting stats and visibility.
- Turnovers (`TOV`): indicates ball control and decision-making, often considered in voting.

Preprocessing steps are implemented in `src/prepare_data.py`.
