#!/usr/bin/env python
"""Fetch GitHub data for the last N days using low API calls.

Endpoints used:
- /search/issues for PRs opened, closed, merged within window
- /search/issues for issues opened, closed within window

Outputs:
- data/prs_opened.csv
- data/prs_closed.csv
- data/prs_merged.csv
- data/issues_opened.csv
- data/issues_closed.csv
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

OWNER = os.getenv("GITHUB_OWNER", "PostHog")
REPO = os.getenv("GITHUB_REPO", "posthog")
BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"
DATA_DIR = Path("data")


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _call(url: str, params: Optional[Dict[str, Any]] = None) -> tuple[Any, requests.Response]:
    resp = requests.get(url, params=params, headers=_headers())
    if resp.status_code == 401:
        raise RuntimeError("GitHub API authentication failed. Check GITHUB_TOKEN.")
    if resp.status_code == 403:
        reset = resp.headers.get("X-RateLimit-Reset")
        if reset:
            reset_time = datetime.utcfromtimestamp(int(reset)).isoformat() + "Z"
            raise RuntimeError(f"GitHub rate limit exceeded. Try again after {reset_time}.")
        raise RuntimeError("GitHub API access forbidden. Check token scopes.")
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    return resp.json(), resp


def _rate_info(resp: requests.Response) -> str:
    remaining = resp.headers.get("X-RateLimit-Remaining", "?")
    limit = resp.headers.get("X-RateLimit-Limit", "?")
    return f"rate_remaining={remaining}/{limit}"


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _write_csv(path: Path, rows: Iterable[Dict[str, Any]], columns: Optional[List[str]] = None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(list(rows), columns=columns)
    df.to_csv(path, index=False)


def _search_issues(query: str, per_page: int) -> Tuple[List[Dict[str, Any]], int]:
    results: List[Dict[str, Any]] = []
    page = 1
    total_count = 0
    while True:
        data, resp = _call(
            "https://api.github.com/search/issues",
            params={
                "q": query,
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "order": "desc",
            },
        )
        print(f"[search] page={page} {_rate_info(resp)}")
        if isinstance(data, dict):
            items = data.get("items", [])
            total_count = data.get("total_count", total_count)
        else:
            items = []
        if not items:
            break
        results.extend(items)
        if len(items) < per_page:
            break
        if page >= 10:
            # Search API only exposes first 1000 results.
            break
        page += 1
    return results, total_count


def _search_issues_windowed(
    query_base: str,
    qualifier: str,
    since: datetime,
    until: datetime,
    per_page: int,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    window_days = 7
    cur = since.date()
    end_date = until.date()

    while cur <= end_date:
        window_end = min(cur + timedelta(days=window_days - 1), end_date)
        q = f"{query_base} {qualifier}:{cur.isoformat()}..{window_end.isoformat()}"
        items, total_count = _search_issues(q, per_page)

        if total_count >= 1000:
            if window_days == 1:
                raise RuntimeError(
                    f"Search window {cur.isoformat()}..{window_end.isoformat()} "
                    f"returned {total_count} results (>=1000). "
                    "Cannot fetch beyond 1000 via search API; reduce scope or change strategy."
                )
            window_days = max(1, window_days // 2)
            continue

        results.extend(items)
        cur = window_end + timedelta(days=1)

    return results


def fetch_prs_opened(since: datetime, per_page: int) -> List[Dict[str, Any]]:
    query = f"repo:{OWNER}/{REPO} is:pr"
    return _search_issues_windowed(query, "created", since, datetime.now(timezone.utc), per_page)


def fetch_prs_closed(since: datetime, per_page: int) -> List[Dict[str, Any]]:
    query = f"repo:{OWNER}/{REPO} is:pr"
    return _search_issues_windowed(query, "closed", since, datetime.now(timezone.utc), per_page)


def fetch_prs_merged(since: datetime, per_page: int) -> List[Dict[str, Any]]:
    query = f"repo:{OWNER}/{REPO} is:pr is:merged"
    return _search_issues_windowed(query, "merged", since, datetime.now(timezone.utc), per_page)


def fetch_issues_opened(since: datetime, per_page: int) -> List[Dict[str, Any]]:
    query = f"repo:{OWNER}/{REPO} is:issue"
    return _search_issues_windowed(query, "created", since, datetime.now(timezone.utc), per_page)


def fetch_issues_closed(since: datetime, per_page: int) -> List[Dict[str, Any]]:
    query = f"repo:{OWNER}/{REPO} is:issue"
    return _search_issues_windowed(query, "closed", since, datetime.now(timezone.utc), per_page)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch minimal GitHub data for impact scoring.")
    parser.add_argument("--days-back", type=int, default=90, help="Days back from now (default: 90).")
    parser.add_argument("--per-page", type=int, default=100, help="Per-page size (default: 100).")
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(days=args.days_back)
    print(f"Fetching data for {OWNER}/{REPO} since {since.isoformat()}")

    prs_opened = fetch_prs_opened(since, args.per_page)
    _write_csv(DATA_DIR / "prs_opened.csv", [
        {
            "pr_number": pr.get("number"),
            "author": pr.get("user", {}).get("login"),
            "created_at": pr.get("created_at"),
            "comments": pr.get("comments"),
        }
        for pr in prs_opened
    ], columns=[
        "pr_number",
        "author",
        "created_at",
        "comments",
    ])
    print(f"PRs opened fetched: {len(prs_opened)}")

    prs_closed = fetch_prs_closed(since, args.per_page)
    _write_csv(DATA_DIR / "prs_closed.csv", [
        {
            "pr_number": pr.get("number"),
            "author": pr.get("user", {}).get("login"),
            "created_at": pr.get("created_at"),
            "closed_at": pr.get("closed_at"),
            "comments": pr.get("comments"),
        }
        for pr in prs_closed
    ], columns=[
        "pr_number",
        "author",
        "created_at",
        "closed_at",
        "comments",
    ])
    print(f"PRs closed fetched: {len(prs_closed)}")

    prs_merged = fetch_prs_merged(since, args.per_page)
    _write_csv(DATA_DIR / "prs_merged.csv", [
        {
            "pr_number": pr.get("number"),
            "author": pr.get("user", {}).get("login"),
            "created_at": pr.get("created_at"),
            "merged_at": pr.get("closed_at"),
            "comments": pr.get("comments"),
        }
        for pr in prs_merged
    ], columns=[
        "pr_number",
        "author",
        "created_at",
        "merged_at",
        "comments",
    ])
    print(f"PRs merged fetched: {len(prs_merged)}")

    issues_opened = fetch_issues_opened(since, args.per_page)
    _write_csv(DATA_DIR / "issues_opened.csv", [
        {
            "issue_number": i.get("number"),
            "opened_by": i.get("user", {}).get("login"),
            "created_at": i.get("created_at"),
            "comments": i.get("comments"),
        }
        for i in issues_opened
    ], columns=[
        "issue_number",
        "opened_by",
        "created_at",
        "comments",
    ])
    print(f"Issues opened fetched: {len(issues_opened)}")

    issues_closed = fetch_issues_closed(since, args.per_page)
    _write_csv(DATA_DIR / "issues_closed.csv", [
        {
            "issue_number": i.get("number"),
            "opened_by": i.get("user", {}).get("login"),
            "created_at": i.get("created_at"),
            "closed_at": i.get("closed_at"),
            "comments": i.get("comments"),
        }
        for i in issues_closed
    ], columns=[
        "issue_number",
        "opened_by",
        "created_at",
        "closed_at",
        "comments",
    ])
    print(f"Issues closed fetched: {len(issues_closed)}")


if __name__ == "__main__":
    main()
