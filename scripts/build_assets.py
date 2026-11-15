#!/usr/bin/env python3
"""Build the static profile SVGs: header and stack card (dark + light).

These rarely change, so they are committed to assets/ rather than rebuilt by
the workflow. Re-run after editing the copy or the stack list below:

  python3 scripts/build_assets.py

Logos are monochrome Simple Icons paths (CC0), fetched once at build time and
inlined, so the published SVGs make no network requests.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import COL, SANS, THEMES, WIDTH, label, svg_open  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ICONS_URL = "https://cdn.jsdelivr.net/npm/simple-icons@13.21.0/icons/{}.svg"

# ---------------------------------------------------------------- content

NAME = ("Arman", "Abir")
HANDLE = "github.com/ArmanAbir2000"
COLUMNS = [
    ("Role", ["Flutter & Laravel developer"], True),
    ("Builds", ["Mobile apps for Android and iOS", "Web platforms and REST APIs"], False),
    ("Core stack", ["Flutter · Dart", "Laravel · PHP · Firebase"], False),
]

STACK = [
    ("Mobile", [("flutter", "Flutter"), ("dart", "Dart"), ("androidstudio", "Android Studio")]),
    ("Backend", [("laravel", "Laravel"), ("php", "PHP"), ("firebase", "Firebase"), ("python", "Python")]),
    ("Data", [("postgresql", "PostgreSQL"), ("mysql", "MySQL")]),
    ("Tooling", [("git", "Git"), ("github", "GitHub"), ("linux", "Linux")]),
]

# ---------------------------------------------------------------- header


def header_svg(theme: str) -> str:
    t = THEMES[theme]
    h = 590
    out = [svg_open(WIDTH, h, f"{' '.join(NAME)} — Flutter and Laravel developer")]

    # The one red element: a solid square mark.
    out.append(f'  <rect x="0" y="0" width="56" height="56" fill="{t["red"]}"/>\n')
    out.append(
        f'  <text x="{WIDTH}" y="38" text-anchor="end" fill="{t["muted"]}" font-family="{SANS}" '
        f'font-size="21">{escape(HANDLE)}</text>\n'
    )

    for i, word in enumerate(NAME):
        out.append(
            f'  <text x="-6" y="{250 + i * 146}" fill="{t["text"]}" font-family="{SANS}" font-size="156" '
            f'font-weight="700" letter-spacing="-7">{escape(word)}</text>\n'
        )

    out.append(f'  <line x1="0" y1="448.5" x2="{WIDTH}" y2="448.5" stroke="{t["rule"]}"/>\n')

    for ci, (title, lines, strong) in enumerate(COLUMNS):
        x = ci * 4 * COL
        out.append(label(t, x, 492, title))
        for li, line in enumerate(lines):
            color, weight = (t["text"], 700) if strong else (t["muted"], 400)
            out.append(
                f'  <text x="{x:g}" y="{530 + li * 34}" fill="{color}" font-family="{SANS}" '
                f'font-size="25" font-weight="{weight}">{escape(line)}</text>\n'
            )

    out.append("</svg>\n")
    return "".join(out)


# ---------------------------------------------------------------- stack


def icon_path(slug: str) -> str:
    req = urllib.request.Request(ICONS_URL.format(slug), headers={"User-Agent": "profile-assets-builder"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        svg = resp.read().decode()
    m = re.search(r'<path d="([^"]+)"', svg)
    if not m:
        raise SystemExit(f"no path in icon {slug}")
    return m.group(1)


def stack_svg(theme: str, paths: dict[str, str]) -> str:
    t = THEMES[theme]
    row_h, size = 84, 32
    h = len(STACK) * row_h + 1
    names = ", ".join(n for _, items in STACK for _, n in items)
    out = [svg_open(WIDTH, h, f"Tech stack: {names}")]

    for ri, (group, items) in enumerate(STACK):
        y0 = ri * row_h
        mid = y0 + row_h / 2
        if ri:
            out.append(f'  <line x1="0" y1="{y0 + 0.5}" x2="{WIDTH}" y2="{y0 + 0.5}" stroke="{t["rule"]}"/>\n')
        out.append(label(t, 0, mid + 5, group))
        for ii, (slug, name) in enumerate(items):
            x = 3 * COL + ii * 2.25 * COL
            scale = size / 24
            out.append(
                f'  <path transform="translate({x:g} {mid - size / 2:g}) scale({scale:g})" '
                f'fill="{t["text"]}" d="{paths[slug]}"/>\n'
                f'  <text x="{x + size + 14:g}" y="{mid + 8:g}" fill="{t["text"]}" font-family="{SANS}" '
                f'font-size="23">{escape(name)}</text>\n'
            )
    out.append(f'  <line x1="0" y1="{h - 0.5}" x2="{WIDTH}" y2="{h - 0.5}" stroke="{t["rule"]}"/>\n')
    out.append("</svg>\n")
    return "".join(out)


# ---------------------------------------------------------------- main


def main() -> int:
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    paths = {slug: icon_path(slug) for _, items in STACK for slug, _ in items}
    for theme in THEMES:
        (out / f"header-{theme}.svg").write_text(header_svg(theme), encoding="utf-8")
        (out / f"stack-{theme}.svg").write_text(stack_svg(theme, paths), encoding="utf-8")
    print(f"wrote header + stack ({len(paths)} icons) -> {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
