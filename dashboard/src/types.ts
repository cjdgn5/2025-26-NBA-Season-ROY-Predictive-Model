export type TrendDirection = "up" | "down" | "flat" | "new";

export type LeaderboardRow = {
  rank: number;
  player_id: number;
  player_name: string;
  team: string | null;
  position: string | null;
  race_odds: number;
  prob_roy_raw: number | null;
  trend_direction: TrendDirection;
  trend_delta: number;
  pts_per_game: number | null;
  reb_per_game: number | null;
  ast_per_game: number | null;
  ts: number | null;
  usg_rate: number | null;
  min_per_game: number | null;
  team_win_pct: number | null;
  points_share: number | null;
  minutes_share: number | null;
  draft_pick_log: number | null;
  draft_tier_display: string | null;
};

export type LeaderboardResponse = {
  run_id: string;
  run_timestamp_utc: string;
  season: string;
  top_n: number;
  odds_sum_current_season: number;
  rows: LeaderboardRow[];
};

export type LatestRunResponse = {
  run_id: string;
  run_timestamp_utc: string;
  season: string;
  model_name: string;
  probability_presentation: string;
  record_count: number;
  odds_sum_current_season: number;
  odds_sum_check_passed: boolean;
};

export type FiltersResponse = {
  season: string;
  teams: string[];
  positions: string[];
  draft_tiers: string[];
};
