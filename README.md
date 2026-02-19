# Engineering Impact Dashboard

A minimal, pragmatic GitHub impact dashboard using a low-API-call approach.

## Setup

```bash
pip install -r requirements.txt
```

Set a GitHub token (recommended):

```bash
export GITHUB_TOKEN=... 
```

## Fetch Data (Low API Calls)

```bash
python fetch_data.py
```

This collects the last 90 days of data via search endpoints only:
- PRs opened / closed / merged
- Issues opened / closed

Outputs CSVs in `data/`.

## Compute Metrics

```bash
python compute_metrics.py
```

Creates `data/engineer_scores.csv`.

## Run Dashboard

```bash
streamlit run app.py
```

## Notes
- Adjust the window: `python fetch_data.py --days-back 90`
- Target a different repo: set `GITHUB_OWNER` and `GITHUB_REPO`
