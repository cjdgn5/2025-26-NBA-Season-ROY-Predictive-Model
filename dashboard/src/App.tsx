import { useEffect, useMemo, useState } from "react";
import type {
  FiltersResponse,
  LatestRunResponse,
  LeaderboardResponse,
  LeaderboardRow
} from "./types";

const API_BASE = "http://127.0.0.1:8000";

function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

function num(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

function trendGlyph(direction: LeaderboardRow["trend_direction"]): string {
  if (direction === "up") return "↑";
  if (direction === "down") return "↓";
  if (direction === "new") return "•";
  return "→";
}

function trendClass(direction: LeaderboardRow["trend_direction"]): string {
  if (direction === "up") return "trend-up";
  if (direction === "down") return "trend-down";
  if (direction === "new") return "trend-new";
  return "trend-flat";
}

export default function App() {
  const [season, setSeason] = useState("2025-26");
  const [topN, setTopN] = useState(10);
  const [teamFilter, setTeamFilter] = useState("");
  const [positionFilter, setPositionFilter] = useState("");
  const [draftTierFilter, setDraftTierFilter] = useState("");
  const [latest, setLatest] = useState<LatestRunResponse | null>(null);
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [board, setBoard] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadLatest() {
      try {
        const response = await fetch(`${API_BASE}/api/v1/runs/latest`);
        if (!response.ok) throw new Error("Failed to load latest run metadata.");
        const data = (await response.json()) as LatestRunResponse;
        setLatest(data);
        setSeason(data.season);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load run metadata.");
      }
    }
    void loadLatest();
  }, []);

  useEffect(() => {
    async function loadFilters() {
      try {
        const response = await fetch(
          `${API_BASE}/api/v1/filters?season=${encodeURIComponent(season)}`
        );
        if (!response.ok) throw new Error("Failed to load filter options.");
        const data = (await response.json()) as FiltersResponse;
        setFilters(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load filters.");
      }
    }
    void loadFilters();
  }, [season]);

  useEffect(() => {
    async function loadLeaderboard() {
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams({
          season,
          top_n: String(topN)
        });
        if (teamFilter) params.set("team", teamFilter);
        if (positionFilter) params.set("position", positionFilter);
        if (draftTierFilter) params.set("draft_tier", draftTierFilter);
        const response = await fetch(`${API_BASE}/api/v1/leaderboard?${params.toString()}`);
        if (!response.ok) {
          const detail = await response.json();
          throw new Error(detail?.error?.message ?? "Failed to load leaderboard.");
        }
        const data = (await response.json()) as LeaderboardResponse;
        setBoard(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load leaderboard.");
      } finally {
        setLoading(false);
      }
    }
    void loadLeaderboard();
  }, [season, topN, teamFilter, positionFilter, draftTierFilter]);

  const bars = useMemo(() => (board?.rows ?? []).slice(0, 10), [board]);

  return (
    <div className="page">
      <header className="header">
        <div>
          <p className="eyebrow">NBA Rookie of the Year Race</p>
          <h1>Leaderboard</h1>
        </div>
        <div className="meta">
          <div>
            <span className="meta-label">Run ID</span>
            <strong>{latest?.run_id ?? board?.run_id ?? "-"}</strong>
          </div>
          <div>
            <span className="meta-label">Updated (UTC)</span>
            <strong>{latest?.run_timestamp_utc ?? board?.run_timestamp_utc ?? "-"}</strong>
          </div>
        </div>
      </header>

      <section className="controls card">
        <div className="control">
          <label>Season</label>
          <input value={season} onChange={(e) => setSeason(e.target.value)} />
        </div>
        <div className="control">
          <label>Top N</label>
          <div className="segmented">
            {[5, 10].map((n) => (
              <button
                key={n}
                className={topN === n ? "active" : ""}
                onClick={() => setTopN(n)}
                type="button"
              >
                Top {n}
              </button>
            ))}
          </div>
        </div>
        <div className="control">
          <label>Team</label>
          <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)}>
            <option value="">All</option>
            {(filters?.teams ?? []).map((team) => (
              <option key={team} value={team}>
                {team}
              </option>
            ))}
          </select>
        </div>
        <div className="control">
          <label>Position</label>
          <select value={positionFilter} onChange={(e) => setPositionFilter(e.target.value)}>
            <option value="">All</option>
            {(filters?.positions ?? []).map((position) => (
              <option key={position} value={position}>
                {position}
              </option>
            ))}
          </select>
        </div>
        <div className="control">
          <label>Draft Tier</label>
          <select value={draftTierFilter} onChange={(e) => setDraftTierFilter(e.target.value)}>
            <option value="">All</option>
            {(filters?.draft_tiers ?? []).map((tier) => (
              <option key={tier} value={tier}>
                {tier}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="summary-grid">
        <article className="card stat-card">
          <p>Season</p>
          <strong>{board?.season ?? season}</strong>
        </article>
        <article className="card stat-card">
          <p>Displayed Odds Sum</p>
          <strong>{pct(board?.odds_sum_current_season, 2)}</strong>
        </article>
        <article className="card stat-card">
          <p>Odds Check</p>
          <strong className={latest?.odds_sum_check_passed ? "ok" : "bad"}>
            {latest?.odds_sum_check_passed ? "Passed" : "Needs Review"}
          </strong>
        </article>
      </section>

      {error ? <div className="error card">{error}</div> : null}

      <section className="content-grid">
        <article className="card chart-card">
          <h2>Top 10 Race Odds</h2>
          <div className="bars">
            {bars.map((row) => (
              <div className="bar-row" key={row.player_id}>
                <span className="bar-label">
                  #{row.rank} {row.player_name}
                </span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${Math.max(row.race_odds * 100, 1)}%` }} />
                </div>
                <span className="bar-value">{pct(row.race_odds, 1)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card table-card">
          <h2>{loading ? "Loading leaderboard..." : "Current Leaderboard"}</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Player</th>
                  <th>Team</th>
                  <th>Odds</th>
                  <th>Trend</th>
                  <th>PTS</th>
                  <th>REB</th>
                  <th>AST</th>
                  <th>TS</th>
                  <th>USG</th>
                  <th>MIN</th>
                  <th>Team Win%</th>
                  <th>Points Share</th>
                  <th>Minutes Share</th>
                </tr>
              </thead>
              <tbody>
                {(board?.rows ?? []).map((row) => (
                  <tr key={row.player_id}>
                    <td>{row.rank}</td>
                    <td className="player">
                      <strong>{row.player_name}</strong>
                      <span>{row.position ?? "-"}</span>
                    </td>
                    <td>{row.team ?? "-"}</td>
                    <td>{pct(row.race_odds, 2)}</td>
                    <td className={trendClass(row.trend_direction)}>
                      {trendGlyph(row.trend_direction)} {pct(row.trend_delta, 2)}
                    </td>
                    <td>{num(row.pts_per_game)}</td>
                    <td>{num(row.reb_per_game)}</td>
                    <td>{num(row.ast_per_game)}</td>
                    <td>{num(row.ts, 3)}</td>
                    <td>{num(row.usg_rate, 1)}</td>
                    <td>{num(row.min_per_game, 1)}</td>
                    <td>{pct(row.team_win_pct, 1)}</td>
                    <td>{pct(row.points_share, 1)}</td>
                    <td>{pct(row.minutes_share, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </div>
  );
}
