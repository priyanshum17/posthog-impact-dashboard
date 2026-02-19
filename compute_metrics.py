#!/usr/bin/env python
"""Compute per-engineer impact metrics from fetched CSVs.

Inputs:
- data/prs_opened.csv
- data/prs_closed.csv
- data/prs_merged.csv
- data/issues_opened.csv
- data/issues_closed.csv

Output:
- data/engineer_scores.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

DATA_DIR = Path("data")

def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


def main() -> None:
    prs_opened = _safe_read_csv(DATA_DIR / "prs_opened.csv")
    prs_closed = _safe_read_csv(DATA_DIR / "prs_closed.csv")
    prs_merged = _safe_read_csv(DATA_DIR / "prs_merged.csv")
    issues_opened = _safe_read_csv(DATA_DIR / "issues_opened.csv")
    issues_closed = _safe_read_csv(DATA_DIR / "issues_closed.csv")

    if prs_opened.empty and prs_closed.empty and prs_merged.empty and issues_opened.empty and issues_closed.empty:
        raise RuntimeError("No input data found. Run fetch_data.py first.")

    metrics = pd.DataFrame()

    if not prs_opened.empty:
        prs_opened_counts = prs_opened.groupby("author").size().rename("prs_opened")
        metrics = pd.concat([metrics, prs_opened_counts], axis=1)

    if not prs_closed.empty:
        prs_closed_counts = prs_closed.groupby("author").size().rename("prs_closed")
        pr_comments = prs_closed["comments"].fillna(0).groupby(prs_closed["author"]).sum().rename("pr_comments")
        metrics = pd.concat([metrics, prs_closed_counts, pr_comments], axis=1)

    if not prs_merged.empty:
        prs_merged_counts = prs_merged.groupby("author").size().rename("prs_merged")
        metrics = pd.concat([metrics, prs_merged_counts], axis=1)

    if not issues_opened.empty:
        issues_opened_counts = issues_opened.groupby("opened_by").size().rename("issues_opened")
        metrics = pd.concat([metrics, issues_opened_counts], axis=1)

    if not issues_closed.empty:
        if "closed_by" in issues_closed.columns:
            issues_closed_counts = issues_closed[issues_closed["closed_by"].notna()].groupby("closed_by").size().rename("issues_closed")
        else:
            # Search API doesn't expose closed_by; fall back to attributing by opener.
            issues_closed_counts = issues_closed[issues_closed["opened_by"].notna()].groupby("opened_by").size().rename("issues_closed")
        metrics = pd.concat([metrics, issues_closed_counts], axis=1)

    metrics = metrics.fillna(0)

    # Normalize key signals to reduce scale differences.
    for col in [
        "prs_merged",
        "prs_closed",
        "issues_closed",
        "prs_opened",
        "issues_opened",
        "pr_comments",
    ]:
        if col in metrics.columns:
            max_val = metrics[col].max()
            if max_val > 0:
                metrics[col + "_norm"] = metrics[col] / max_val
            else:
                metrics[col + "_norm"] = 0.0
        else:
            metrics[col] = 0
            metrics[col + "_norm"] = 0.0

    # Simple, explainable weighting.
    metrics["impact_score"] = (
        0.45 * metrics["prs_merged_norm"]
        + 0.15 * metrics["prs_closed_norm"]
        + 0.15 * metrics["issues_closed_norm"]
        + 0.10 * metrics["prs_opened_norm"]
        + 0.10 * metrics["issues_opened_norm"]
        + 0.05 * metrics["pr_comments_norm"]
    ).round(4)

    metrics = metrics.sort_values("impact_score", ascending=False)
    metrics["rank"] = range(1, len(metrics) + 1)

    metrics = metrics.reset_index().rename(columns={"index": "engineer"})
    metrics.to_csv(DATA_DIR / "engineer_scores.csv", index=False)
    print("Wrote data/engineer_scores.csv")


if __name__ == "__main__":
    main()
