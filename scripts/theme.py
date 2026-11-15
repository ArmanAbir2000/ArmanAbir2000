"""Shared design tokens for every SVG on the profile.

Swiss editorial system: transparent backgrounds (the SVGs sit directly on
GitHub's page), hairline rules, a 12-column grid on a 1200px canvas, one red
accent. Dark variants are shown to dark-mode visitors, light to light-mode.
"""

WIDTH = 1200
COL = WIDTH / 12  # 100px grid column

SANS = "Helvetica Neue, Helvetica, Arial, Liberation Sans, sans-serif"

THEMES = {
    "dark": {
        "text": "#F5F5F5",
        "muted": "#A3A3A3",
        "faint": "#6E7681",
        "rule": "#30363D",
        "red": "#E5243B",
        # NONE, FIRST_QUARTILE, SECOND_QUARTILE, THIRD_QUARTILE, FOURTH_QUARTILE
        "levels": ["#21262D", "#5C0E18", "#9A1528", "#D81E34", "#FF5263"],
    },
    "light": {
        "text": "#0A0A0A",
        "muted": "#4D4D4D",
        "faint": "#7D8590",
        "rule": "#D0D7DE",
        "red": "#D0142C",
        "levels": ["#EBEDF0", "#FFC9CF", "#FF7A88", "#E5243B", "#A3101F"],
    },
}


def svg_open(width: float, height: float, label: str) -> str:
    from html import escape

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}" role="img" aria-label="{escape(label)}">\n'
        f"  <title>{escape(label)}</title>\n"
    )


def label(t: dict, x: float, y: float, text: str, anchor: str = "start") -> str:
    """Small uppercase caption used above values (ROLE, CONTRIBUTIONS, ...)."""
    from html import escape

    return (
        f'  <text x="{x:g}" y="{y:g}" text-anchor="{anchor}" fill="{t["faint"]}" '
        f'font-family="{SANS}" font-size="15" font-weight="700" letter-spacing="1.5">'
        f"{escape(text.upper())}</text>\n"
    )
