#!/usr/bin/env python3
"""
AFCON fantasy round scraper (shareable-safe defaults).

Fetches players from a specific fantasy round (defaults to AFCON round 803) via:
    https://www.sofascore.com/api/v1/fantasy/round/{round_id}/players

How to supply required headers (do this in your browser):
- Open DevTools → Network, filter for "round/803/players" (or your round id).
- Click the request and copy:
    * X-Requested-With (numeric token)
    * Cookie (includes cf_clearance and session cookies)
    * If present: Origin / Sec-Fetch-* headers
- Pass them to this script via:
    --x-requested-with <value>
    --cookie "<cookie string>"
    --header KEY=VALUE (repeatable) for any extra headers you saw.

Notes:
- Uses plain HTTP requests (no Selenium/undetected_chromedriver).
- Paginates through all pages for the requested positions.
- Supports ownership filtering, sorting, CSV output, and optional raw JSON save.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import requests


ROUND_PLAYERS_URL_TEMPLATE = "https://www.sofascore.com/api/v1/fantasy/round/{round_id}/players"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_REQUESTED_WITH = ""  # leave blank; supply from DevTools Network
DEFAULT_ACCEPT = "application/json, text/plain, */*"
DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
DEFAULT_REFERER = "https://www.sofascore.com/"


def build_headers(
    x_requested_with: str,
    user_agent: str,
    accept: str,
    accept_language: str,
    referer: str,
    cookie: Optional[str],
    extra_headers: Optional[Dict[str, str]],
) -> Dict[str, str]:
    headers = {
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Language": accept_language,
        "Referer": referer,
    }
    if x_requested_with:
        headers["X-Requested-With"] = x_requested_with
    if cookie:
        headers["Cookie"] = cookie
    if extra_headers:
        headers.update(extra_headers)
    return headers


def fetch_round_page(
    round_id: int,
    position: Optional[str],
    page: int,
    results_per_page: int,
    sort_param: str,
    sort_order: str,
    headers: Dict[str, str],
    timeout: float,
) -> Dict[str, Any]:
    url = ROUND_PLAYERS_URL_TEMPLATE.format(round_id=round_id)
    params: Dict[str, Any] = {
        "page": page,
        "resultsPerPage": results_per_page,
        "sortParam": sort_param,
        "sortOrder": sort_order,
    }
    if position and position != "ALL":
        params["position"] = position

    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_round_players(
    round_id: int,
    positions: Sequence[str],
    results_per_page: int,
    sort_param: str,
    sort_order: str,
    headers: Dict[str, str],
    timeout: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fetch all pages for the given positions."""
    all_players: List[Dict[str, Any]] = []
    raw_pages: List[Dict[str, Any]] = []

    for pos in positions:
        page = 0
        while True:
            payload = fetch_round_page(
                round_id=round_id,
                position=pos,
                page=page,
                results_per_page=results_per_page,
                sort_param=sort_param,
                sort_order=sort_order,
                headers=headers,
                timeout=timeout,
            )
            raw_pages.append({"position": pos, "page": page, "payload": payload})

            players = payload.get("players") or []
            all_players.extend(players)

            if not payload.get("hasNextPage"):
                break
            page += 1

    return all_players, raw_pages


def normalize_player_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested fantasy player data into a simple row."""
    fantasy = entry.get("fantasyPlayer") or {}
    player = fantasy.get("player") or entry.get("player") or {}
    team = fantasy.get("team") or entry.get("team") or {}
    fixtures = entry.get("fixtures") or []

    def _ts(f: Dict[str, Any]) -> Any:
        return f.get("eventStartTimestamp")

    fixtures_sorted = sorted(
        [f for f in fixtures if f.get("eventStartTimestamp") is not None],
        key=_ts,
    )
    next_fixture = fixtures_sorted[0] if fixtures_sorted else (fixtures[0] if fixtures else {})
    next_start_ts = next_fixture.get("eventStartTimestamp")
    next_fixture_team = next_fixture.get("team") or {}

    return {
        "player_id": player.get("id"),
        "name": player.get("name"),
        "slug": player.get("slug"),
        "position": player.get("position"),
        "team": team.get("name"),
        "team_id": team.get("id"),
        "price": entry.get("price") or fantasy.get("price"),
        "expected_points": entry.get("expectedPoints"),
        "average_score": fantasy.get("averageScore"),
        "average_score_rank": fantasy.get("averageScoreRank"),
        "total_points": fantasy.get("totalScore") or fantasy.get("totalPoints"),
        "total_points_rank": fantasy.get("totalScoreRank"),
        "form": fantasy.get("form"),
        "form_rank": fantasy.get("formRank"),
        "owned_percentage": fantasy.get("ownedPercentage"),
        "owned_count": fantasy.get("ownedCount"),
        "owned_rank": fantasy.get("ownedRank"),
        "adds": fantasy.get("adds"),
        "drops": fantasy.get("drops"),
        "total_players_on_position": fantasy.get("totalPlayersOnPosition"),
        "has_left_competition": fantasy.get("hasLeftCompetition"),
        "round_player_id": entry.get("roundPlayerId"),
        "fantasy_id": fantasy.get("id") or entry.get("id"),
        "status": fantasy.get("status"),
        "fixture_difficulty": next_fixture.get("fixtureDifficulty"),
        "event_id": next_fixture.get("eventId"),
        "event_start_timestamp": next_start_ts,
        "event_start_iso_utc": (
            datetime.utcfromtimestamp(next_start_ts).isoformat() + "Z"
            if next_start_ts
            else None
        ),
        "fixtures_count": len(fixtures),
        "next_opponent": next_fixture_team.get("name"),
        "next_opponent_id": next_fixture_team.get("id"),
    }


def normalize_market(players: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """Convert the players list into a DataFrame."""
    rows: List[Dict[str, Any]] = [normalize_player_entry(entry) for entry in players]
    if not rows:
        raise ValueError("No players found in the market payload.")
    return pd.DataFrame(rows)


def filter_by_ownership(
    df: pd.DataFrame,
    min_ownership: Optional[float],
    max_ownership: Optional[float],
) -> pd.DataFrame:
    """Filter players by ownership percentage bounds."""
    filtered = df.copy()
    if min_ownership is not None:
        filtered = filtered[filtered["owned_percentage"].fillna(0) >= min_ownership]
    if max_ownership is not None:
        filtered = filtered[filtered["owned_percentage"].fillna(0) <= max_ownership]
    return filtered


def write_outputs(
    df: pd.DataFrame,
    csv_path: Path,
    raw_json: Optional[Dict[str, Any]] = None,
    raw_json_path: Optional[Path] = None,
) -> None:
    """Persist the processed CSV and optional raw JSON."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)

    if raw_json is not None and raw_json_path is not None:
        raw_json_path.parent.mkdir(parents=True, exist_ok=True)
        raw_json_path.write_text(json.dumps(raw_json, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape AFCON fantasy market data from SofaScore (shareable-safe defaults).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--round-id",
        type=int,
        default=803,
        help="Fantasy round id to target.",
    )
    parser.add_argument(
        "--x-requested-with",
        default=DEFAULT_REQUESTED_WITH,
        help="X-Requested-With header value captured from the site.",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header to send with the request.",
    )
    parser.add_argument(
        "--accept",
        default=DEFAULT_ACCEPT,
        help="Accept header to send with the request.",
    )
    parser.add_argument(
        "--accept-language",
        default=DEFAULT_ACCEPT_LANGUAGE,
        help="Accept-Language header to send with the request.",
    )
    parser.add_argument(
        "--referer",
        default=DEFAULT_REFERER,
        help="Referer header to send with the request.",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Optional Cookie header (copy from browser if the endpoint is challenged).",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=None,
        metavar="KEY=VALUE",
        help="Extra header(s) to include. Can be passed multiple times.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--min-ownership",
        type=float,
        default=None,
        help="Minimum ownership percentage to include.",
    )
    parser.add_argument(
        "--max-ownership",
        type=float,
        default=None,
        help="Maximum ownership percentage to include.",
    )
    parser.add_argument(
        "--sort-by",
        choices=["price", "average_score", "owned_percentage", "form", "total_points", "expected_points"],
        default="price",
        help="Column to sort the output by (descending).",
    )
    parser.add_argument(
        "--sort-param",
        choices=["price", "averageScore", "ownedPercentage", "form", "totalScore", "expectedPoints"],
        default="price",
        help="Sort parameter to send to the API.",
    )
    parser.add_argument(
        "--sort-order",
        choices=["ASC", "DESC"],
        default="DESC",
        help="Sort order to send to the API.",
    )
    parser.add_argument(
        "--results-per-page",
        type=int,
        default=200,
        help="Results per page for API pagination.",
    )
    parser.add_argument(
        "--positions",
        default="F,M,D,G",
        help="Comma-separated positions to fetch (use ALL for no position filter).",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/afcon/afcon_fantasy_market.csv"),
        help="Where to save the processed CSV.",
    )
    parser.add_argument(
        "--raw-json",
        type=Path,
        default=None,
        help="Optional path to save the raw market JSON.",
    )
    parser.add_argument(
        "--print-top",
        type=int,
        default=10,
        help="Print the top N rows after sorting (set 0 to skip).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    positions = [p.strip().upper() for p in args.positions.split(",") if p.strip()]
    if not positions:
        positions = ["ALL"]

    extra_headers: Dict[str, str] = {}
    if args.header:
        for raw in args.header:
            if "=" not in raw:
                raise SystemExit(f"Invalid header format (use KEY=VALUE): {raw}")
            key, value = raw.split("=", 1)
            extra_headers[key.strip()] = value.strip()

    headers = build_headers(
        x_requested_with=args.x_requested_with,
        user_agent=args.user_agent,
        accept=args.accept,
        accept_language=args.accept_language,
        referer=args.referer,
        cookie=args.cookie,
        extra_headers=extra_headers or None,
    )

    try:
        players, raw_pages = fetch_round_players(
            round_id=args.round_id,
            positions=positions,
            results_per_page=args.results_per_page,
            sort_param=args.sort_param,
            sort_order=args.sort_order,
            headers=headers,
            timeout=args.timeout,
        )
    except Exception as exc:
        raise SystemExit(f"Error fetching market data: {exc}")

    try:
        df = normalize_market(players)
    except Exception as exc:
        raise SystemExit(f"Error normalizing market payload: {exc}")

    df = filter_by_ownership(
        df,
        min_ownership=args.min_ownership,
        max_ownership=args.max_ownership,
    )

    if df.empty:
        raise SystemExit("No players left after applying filters.")

    df = df.sort_values(by=args.sort_by, ascending=False)

    csv_path: Path = args.output_csv
    if csv_path == Path("data/afcon/afcon_fantasy_market.csv"):
        today = datetime.utcnow().strftime("%Y%m%d")
        csv_path = csv_path.with_name(f"{csv_path.stem}_{today}{csv_path.suffix}")

    raw_json_payload: Optional[Dict[str, Any]] = None
    if args.raw_json:
        raw_json_payload = {"pages": raw_pages}

    write_outputs(df, csv_path, raw_json=raw_json_payload, raw_json_path=args.raw_json)

    if args.print_top > 0:
        print(df.head(args.print_top).to_string(index=False))
    print(f"Saved {len(df)} players to {csv_path}")
    if args.raw_json:
        print(f"Raw payload saved to {args.raw_json}")


if __name__ == "__main__":
    main()
