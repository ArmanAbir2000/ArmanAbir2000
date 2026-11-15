#!/usr/bin/env python3
"""Render red / black / white profile cards from the GitHub GraphQL API.

Outputs (into --out, default ./dist):
  stats-dark.svg      stats-light.svg
  activity-dark.svg   activity-light.svg

Usage:
  GITHUB_TOKEN=... python3 scripts/generate_cards.py --user ArmanAbir2000
  python3 scripts/generate_cards.py --mock          # local preview, no API call

Standard library only, so it runs on any GitHub Actions runner without installs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from html import escape
from pathlib import Path

# ---------------------------------------------------------------- theme tokens

THEMES = {
    "dark": {
        "bg": "#0A0A0A",
        "border": "#262626",
        "text": "#FAFAFA",
        "muted": "#A3A3A3",
        "faint": "#525252",
        "red": "#E11D2E",
        # NONE, FIRST_QUARTILE, SECOND_QUARTILE, THIRD_QUARTILE, FOURTH_QUARTILE
        "levels": ["#171717", "#4C0A13", "#86101F", "#C8152B", "#FF3B4E"],
    },
    "light": {
        "bg": "#FFFFFF",
        "border": "#E5E5E5",
        "text": "#0A0A0A",
        "muted": "#525252",
        "faint": "#A3A3A3",
        "red": "#C8102E",
        "levels": ["#F0F0F0", "#FECDD3", "#FB7185", "#E11D2E", "#9F1020"],
    },
}

LEVEL_INDEX = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

SANS = "Segoe UI, -apple-system, BlinkMacSystemFont, Helvetica Neue, Arial, sans-serif"
MONO = "SFMono-Regular, Consolas, Liberation Mono, Menlo, monospace"

WIDTH = 1200

# ---------------------------------------------------------------- data

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount contributionLevel }
        }
      }
    }
  }
}
"""


def fetch(login: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    user = payload["data"]["user"]
    if user is None:
        raise SystemExit(f"User not found: {login}")
    return user["contributionsCollection"]


def mock() -> dict:
    rng = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364 + (today.weekday() + 1) % 7)
    weeks, week, total = [], [], 0
    day = start
    while day <= today:
        n = rng.choice([0, 0, 0, 1, 2, 3, 5, 8, 12]) if day.weekday() < 6 else rng.choice([0, 0, 1, 4])
        total += n
        lvl = "NONE" if n == 0 else ["FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"][min(3, n // 3)]
        week.append({"date": day.isoformat(), "contributionCount": n, "contributionLevel": lvl})
        if len(week) == 7:
            weeks.append({"contributionDays": week})
            week = []
        day += dt.timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})
    return {
        "totalCommitContributions": int(total * 0.7),
        "restrictedContributionsCount": 0,
        "contributionCalendar": {"totalContributions": total, "weeks": weeks},
    }


def summarize(collection: dict) -> dict:
    cal = collection["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])

    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)

    # Current streak: walk back from today; an empty "today" does not break it.
    current = 0
    idx = len(days) - 1
    if idx >= 0 and days[idx]["contributionCount"] == 0:
        idx -= 1
    while idx >= 0 and days[idx]["contributionCount"] > 0:
        current += 1
        idx -= 1

    active = sum(1 for d in days if d["contributionCount"] > 0)
    best = max(days, key=lambda d: d["contributionCount"]) if days else None

    return {
        "total": cal["totalContributions"],
        "commits": collection["totalCommitContributions"] + collection["restrictedContributionsCount"],
        "current": current,
        "longest": longest,
        "active": active,
        "best": best["contributionCount"] if best else 0,
        "weeks": cal["weeks"],
    }


# ---------------------------------------------------------------- rendering


def fmt(n: int) -> str:
    return f"{n:,}"


def frame(t: dict, height: int, body: str, label: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(label)}">
  <title>{escape(label)}</title>
  <defs><clipPath id="c"><rect x="0" y="0" width="{WIDTH}" height="{height}" rx="10"/></clipPath></defs>
  <g clip-path="url(#c)">
    <rect width="{WIDTH}" height="{height}" fill="{t['bg']}"/>
    <rect x="0" y="0" width="4" height="{height}" fill="{t['red']}"/>
  </g>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="10" fill="none" stroke="{t['border']}"/>
{body}
</svg>
"""


def header_row(t: dict, title: str, right: str) -> str:
    return f"""  <text x="40" y="44" fill="{t['muted']}" font-family="{MONO}" font-size="13" letter-spacing="2">{escape(title)}</text>
  <text x="{WIDTH - 40}" y="44" text-anchor="end" fill="{t['faint']}" font-family="{MONO}" font-size="12" letter-spacing="1">{escape(right)}</text>
  <line x1="40" y1="62" x2="{WIDTH - 40}" y2="62" stroke="{t['border']}"/>"""


def stats_svg(s: dict, theme: str, updated: str) -> str:
    t = THEMES[theme]
    metrics = [
        ("CONTRIBUTIONS", fmt(s["total"]), "last 12 months"),
        ("CURRENT STREAK", fmt(s["current"]), "days" if s["current"] != 1 else "day"),
        ("LONGEST STREAK", fmt(s["longest"]), "days" if s["longest"] != 1 else "day"),
        ("ACTIVE DAYS", fmt(s["active"]), f"best day: {fmt(s['best'])}"),
    ]
    col_w = (WIDTH - 80) / len(metrics)
    parts = [header_row(t, "GITHUB ACTIVITY", f"UPDATED {updated}")]
    for i, (label, value, sub) in enumerate(metrics):
        x = 40 + i * col_w
        accent = t["red"] if i == 1 else t["text"]
        if i:
            parts.append(f'  <line x1="{x:.1f}" y1="88" x2="{x:.1f}" y2="176" stroke="{t["border"]}"/>')
        pad = 0 if i == 0 else 28
        parts.append(
            f"""  <text x="{x + pad:.1f}" y="104" fill="{t['muted']}" font-family="{MONO}" font-size="12" letter-spacing="1.5">{label}</text>
  <text x="{x + pad:.1f}" y="152" fill="{accent}" font-family="{SANS}" font-size="44" font-weight="700">{value}</text>
  <text x="{x + pad:.1f}" y="176" fill="{t['faint']}" font-family="{MONO}" font-size="12">{escape(sub)}</text>"""
        )
    return frame(t, 210, "\n".join(parts), f"GitHub activity: {s['total']} contributions in the last year")


def activity_svg(s: dict, theme: str) -> str:
    t = THEMES[theme]
    cell, gap = 16, 4
    step = cell + gap
    weeks = s["weeks"][-53:]
    grid_w = len(weeks) * step - gap
    left = (WIDTH - grid_w) / 2 + 16
    top = 110

    parts = [header_row(t, "CONTRIBUTION GRAPH", f"{fmt(s['total'])} IN THE LAST YEAR")]

    # Month labels at the first week that starts a new month.
    last_month = None
    for wi, w in enumerate(weeks):
        first = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != last_month:
            last_month = first.month
            if wi < len(weeks) - 2:
                parts.append(
                    f'  <text x="{left + wi * step:.1f}" y="{top - 14}" fill="{t["muted"]}" font-family="{MONO}" font-size="12">{first.strftime("%b")}</text>'
                )

    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        parts.append(
            f'  <text x="{left - 12:.1f}" y="{top + row * step + 12}" text-anchor="end" fill="{t["faint"]}" font-family="{MONO}" font-size="11">{name}</text>'
        )

    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            wd = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday = 0
            color = t["levels"][LEVEL_INDEX.get(d["contributionLevel"], 0)]
            n = d["contributionCount"]
            tip = f'{n} contribution{"s" if n != 1 else ""} on {d["date"]}'
            parts.append(
                f'  <rect x="{left + wi * step:.1f}" y="{top + wd * step}" width="{cell}" height="{cell}" rx="3" fill="{color}"><title>{tip}</title></rect>'
            )

    # Legend
    ly = top + 7 * step + 18
    lx = WIDTH - 40 - (5 * step - gap) - 44
    parts.append(f'  <text x="{lx - 10}" y="{ly + 12}" text-anchor="end" fill="{t["faint"]}" font-family="{MONO}" font-size="11">Less</text>')
    for i, c in enumerate(t["levels"]):
        parts.append(f'  <rect x="{lx + i * step}" y="{ly}" width="{cell}" height="{cell}" rx="3" fill="{c}"/>')
    parts.append(f'  <text x="{lx + 5 * step + 6}" y="{ly + 12}" fill="{t["faint"]}" font-family="{MONO}" font-size="11">More</text>')

    height = ly + cell + 30
    return frame(t, height, "\n".join(parts), f"Contribution graph: {s['total']} contributions in the last year")


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_USER", "ArmanAbir2000"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--mock", action="store_true", help="render with fake data, no API call")
    args = ap.parse_args()

    if args.mock:
        collection = mock()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("GITHUB_TOKEN is not set (use --mock for a local preview)", file=sys.stderr)
            return 1
        collection = fetch(args.user, token)

    s = summarize(collection)
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (out / f"stats-{theme}.svg").write_text(stats_svg(s, theme, updated), encoding="utf-8")
        (out / f"activity-{theme}.svg").write_text(activity_svg(s, theme), encoding="utf-8")
    print(f"total={s['total']} current={s['current']} longest={s['longest']} active={s['active']} -> {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
