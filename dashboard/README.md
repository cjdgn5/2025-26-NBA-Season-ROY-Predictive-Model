# ROY Dashboard (Leaderboard V1)

React + Vite frontend for the NBA ROY leaderboard.

## Prerequisites

1. API service running at `http://127.0.0.1:8000`
2. Node.js installed

## Run Locally (CMD)

```cmd
cd dashboard
npm install
npm run dev
```

Vite default URL: `http://127.0.0.1:5173`

## Build

```cmd
cd dashboard
npm run build
```

## Current Scope

- Leaderboard page with:
  - Top 5 / Top 10 toggle
  - Season input
  - Team / Position / Draft Tier filters
  - Top-10 probability bar chart
  - Traceability metadata (`run_id`, `run_timestamp_utc`)
  - Data table including player and team context features
