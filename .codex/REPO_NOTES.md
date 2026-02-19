# Repo Memory: Engineering Impact Dashboard

Purpose
- Minimal Streamlit dashboard to rank engineer impact from GitHub PR/issue activity with low API calls.

Core Flow
1. `fetch_data.py` calls GitHub Search API for the last N days and writes CSVs into `data/`.
2. `compute_metrics.py` aggregates CSVs into `data/engineer_scores.csv` with normalized metrics and a weighted impact score.
3. `app.py` loads `data/engineer_scores.csv` and renders the Streamlit dashboard.

Architecture Overview
- Data collection: `fetch_data.py`
  - Uses `https://api.github.com/search/issues` only.
  - Windowed by date range (default 7-day windows) to avoid 1000-result Search API limit.
  - Writes: `prs_opened.csv`, `prs_closed.csv`, `prs_merged.csv`, `issues_opened.csv`, `issues_closed.csv`.
- Metrics: `compute_metrics.py`
  - Reads the above CSVs safely (empty/missing -> empty DataFrame).
  - Produces per-engineer counts + normalized columns.
  - `impact_score` weights:
    - PRs merged 45%
    - PRs closed 15%
    - Issues closed 15%
    - PRs opened 10%
    - Issues opened 10%
    - PR comments 5%
  - Outputs: `data/engineer_scores.csv` with `rank` and `engineer` columns.
- UI: `app.py`
  - Streamlit dashboard with custom CSS and Plotly bar charts.
  - Reads `data/engineer_scores.csv` only.
  - Shows Top 5 leaderboard and charts, plus scoring model and FAQ.

Key Files
- `README.md`: setup/run commands + deployment note.
- `fetch_data.py`: GitHub Search API fetch with rate-limit handling.
- `compute_metrics.py`: aggregation + scoring model.
- `app.py`: Streamlit UI and visuals.
- `data/`: committed CSVs for static/demo mode.

Data Contracts
- `data/prs_opened.csv`: `pr_number, author, created_at, comments`
- `data/prs_closed.csv`: `pr_number, author, created_at, closed_at, comments`
- `data/prs_merged.csv`: `pr_number, author, created_at, merged_at, comments`
- `data/issues_opened.csv`: `issue_number, opened_by, created_at, comments`
- `data/issues_closed.csv`: `issue_number, opened_by, created_at, closed_at, comments`
- `data/engineer_scores.csv`: `engineer, impact_score, rank` plus metric columns (`prs_merged`, `prs_closed`, `issues_closed`, `prs_opened`, `issues_opened`, `pr_comments`, and their `_norm` versions).

Environment/Config
- `GITHUB_TOKEN` optional but recommended. If missing, unauthenticated rate limits apply.
- `GITHUB_OWNER` / `GITHUB_REPO` to target a different repo (defaults: `PostHog/posthog`).
- `fetch_data.py --days-back N` to change window (default 90 days).

Limitations / Assumptions
- Search API doesn’t expose `closed_by` for issues; `issues_closed` is attributed to the opener as a proxy.
- Search API returns max 1000 results per query; script reduces window size if needed.
- `app.py` assumes `data/engineer_scores.csv` exists and is non-empty.
- “Static mode” depends on committed CSVs in `data/` for hosted demo.

Quick Commands
- Install deps: `pip install -r requirements.txt`
- Fetch data: `python fetch_data.py --days-back 90`
- Compute metrics: `python compute_metrics.py`
- Run app: `streamlit run app.py`

Notes for Future Agents
- If results look empty, check `GITHUB_TOKEN` and Search API rate limit errors.
- Adding true `issues_closed` by closer would require per-issue API calls (higher cost).
- There are legacy CSVs (`data/prs.csv`, `data/issues.csv`, `data/review_comments.csv`) not used by the current pipeline.
