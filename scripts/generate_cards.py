#!/usr/bin/env python3
"""Render the profile activity cards (red / black / white, see theme.py).

Outputs (into --out, default ./dist):
  stats-dark.svg      stats-light.svg
  activity-dark.svg   activity-light.svg

Data source: the public contribution calendar (includes private counts when
the profile setting is on), with the GraphQL API as a fallback.

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
import re
import sys
import urllib.request
from html import escape
from pathlib import Path

# ---------------------------------------------------------------- theme tokens

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import COL, SANS, THEMES, WIDTH, label, svg_open  # noqa: E402

LEVEL_INDEX = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

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


LEVEL_NAMES = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]


def fetch_public(login: str) -> dict:
    """Read the contribution calendar shown on the public profile.

    This page includes private contributions (as anonymous counts) when the
    user enabled "Include private contributions on my profile". The Actions
    GITHUB_TOKEN cannot see those through the GraphQL API, so this is the
    primary source.
    """
    req = urllib.request.Request(
        f"https://github.com/users/{login}/contributions",
        headers={"User-Agent": "profile-cards-generator"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")

    cells = {}
    for tag in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", html):
        date = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        cid = re.search(r'id="([^"]+)"', tag)
        level = re.search(r'data-level="(\d)"', tag)
        if date and cid and level:
            cells[cid.group(1)] = {"date": date.group(1), "level": int(level.group(1))}

    counts = {}
    for cid, text in re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
        m = re.match(r"\s*([\d,]+) contributions?", text)
        counts[cid] = int(m.group(1).replace(",", "")) if m else 0

    if len(cells) < 300 or not counts:
        raise ValueError(f"unexpected contributions markup ({len(cells)} days parsed)")

    days = sorted(
        (
            {
                "date": c["date"],
                "contributionCount": counts.get(cid, 0),
                "contributionLevel": LEVEL_NAMES[min(c["level"], 4)],
            }
            for cid, c in cells.items()
        ),
        key=lambda d: d["date"],
    )

    weeks, week = [], []
    for d in days:
        if week and dt.date.fromisoformat(d["date"]).weekday() == 6:  # Sunday starts a week
            weeks.append({"contributionDays": week})
            week = []
        week.append(d)
    if week:
        weeks.append({"contributionDays": week})

    total = sum(d["contributionCount"] for d in days)
    return {
        "totalCommitContributions": 0,
        "restrictedContributionsCount": 0,
        "contributionCalendar": {"totalContributions": total, "weeks": weeks},
    }


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


def plural(n: int, word: str) -> str:
    return f"{word}{'' if n == 1 else 's'}"


def stats_svg(s: dict, theme: str) -> str:
    """Four figures on the 12-column grid (3 columns each), hairline on top."""
    t = THEMES[theme]
    metrics = [
        ("Contributions", s["total"], "in the last 12 months"),
        ("Current streak", s["current"], plural(s["current"], "day")),
        ("Longest streak", s["longest"], plural(s["longest"], "day")),
        ("Active days", s["active"], f"busiest day: {fmt(s['best'])}"),
    ]
    h = 180
    out = [svg_open(WIDTH, h, f"GitHub activity: {fmt(s['total'])} contributions in the last year")]
    for i, (name, value, sub) in enumerate(metrics):
        x = i * 3 * COL
        out.append(label(t, x, 34, name))
        out.append(
            f'  <text x="{x:g}" y="112" fill="{t["text"]}" font-family="{SANS}" font-size="72" '
            f'font-weight="700" letter-spacing="-2">{fmt(value)}</text>\n'
            f'  <text x="{x:g}" y="152" fill="{t["muted"]}" font-family="{SANS}" font-size="21">{escape(sub)}</text>\n'
        )
    out.append("</svg>\n")
    return "".join(out)


def activity_svg(s: dict, theme: str, updated: str) -> str:
    """Contribution graph in the red scale, with range + legend underneath."""
    t = THEMES[theme]
    weeks = s["weeks"][-53:]
    left, top, gap = 44, 62, 4
    step = (WIDTH - left + gap) / 53  # graph spans the full width
    cell = step - gap
    h = top + 7 * step + 66

    out = [svg_open(WIDTH, h, f"Contribution graph: {fmt(s['total'])} contributions in the last year")]
    out.append(f'  <line x1="0" y1="0.5" x2="{WIDTH}" y2="0.5" stroke="{t["rule"]}"/>\n')

    last_month = None
    for wi, w in enumerate(weeks):
        first = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != last_month:
            last_month = first.month
            if wi < len(weeks) - 2:
                out.append(
                    f'  <text x="{left + wi * step:g}" y="42" fill="{t["muted"]}" font-family="{SANS}" '
                    f'font-size="17">{first.strftime("%b")}</text>\n'
                )

    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(
            f'  <text x="0" y="{top + row * step + cell - 3:g}" fill="{t["faint"]}" font-family="{SANS}" '
            f'font-size="15">{name}</text>\n'
        )

    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            wd = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday = 0
            color = t["levels"][LEVEL_INDEX.get(d["contributionLevel"], 0)]
            n = d["contributionCount"]
            out.append(
                f'  <rect x="{left + wi * step:.1f}" y="{top + wd * step:.1f}" width="{cell:.1f}" height="{cell:.1f}" '
                f'rx="2" fill="{color}"><title>{n} {plural(n, "contribution")} on {d["date"]}</title></rect>\n'
            )

    first_day = dt.date.fromisoformat(weeks[0]["contributionDays"][0]["date"])
    last_day = dt.date.fromisoformat(weeks[-1]["contributionDays"][-1]["date"])
    fy = round(top + 7 * step + 42)
    out.append(
        f'  <text x="0" y="{fy}" fill="{t["faint"]}" font-family="{SANS}" font-size="17">'
        f'{first_day.strftime("%b %Y")} – {last_day.strftime("%b %Y")}  ·  updated {updated}</text>\n'
    )
    ls = 18  # legend swatch
    lx = WIDTH - 5 * (ls + gap) - 54
    out.append(
        f'  <text x="{lx - 10}" y="{fy}" text-anchor="end" fill="{t["faint"]}" font-family="{SANS}" font-size="17">Less</text>\n'
    )
    for i, c in enumerate(t["levels"]):
        out.append(f'  <rect x="{lx + i * (ls + gap)}" y="{fy - 15}" width="{ls}" height="{ls}" rx="2" fill="{c}"/>\n')
    out.append(
        f'  <text x="{WIDTH}" y="{fy}" text-anchor="end" fill="{t["faint"]}" font-family="{SANS}" font-size="17">More</text>\n'
    )
    out.append("</svg>\n")
    return "".join(out)


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
        try:
            collection = fetch_public(args.user)
        except Exception as exc:  # markup changed or network issue: fall back to the API
            print(f"public calendar unavailable ({exc}); falling back to GraphQL", file=sys.stderr)
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
        (out / f"stats-{theme}.svg").write_text(stats_svg(s, theme), encoding="utf-8")
        (out / f"activity-{theme}.svg").write_text(activity_svg(s, theme, updated), encoding="utf-8")
    print(f"total={s['total']} current={s['current']} longest={s['longest']} active={s['active']} -> {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
