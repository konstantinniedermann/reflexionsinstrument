"""Kontraste der Farbvariablen nach WCAG AA, im hellen und im dunklen Farbschema (#20)."""

import re
from pathlib import Path

import pytest

CSS = (Path(__file__).parent.parent / "app" / "static" / "css" / "style.css").read_text(
    encoding="utf-8"
)

# Schrift auf Hintergrund, wie sie im Stylesheet vorkommen.
PAARE = [
    ("tinte", "papier"),
    ("tinte", "karte"),
    ("gedaempft", "papier"),
    ("gedaempft", "karte"),
    ("akzent-text", "akzent"),
    ("akzent", "karte"),
    ("akzent", "papier"),
    ("erledigt", "erledigt-sanft"),
    ("fehler", "karte"),
    ("fehler", "papier"),
    ("hinweis-linie", "hinweis"),
    ("auf-runden", "farbe-runden"),
    ("auf-tagebuch", "farbe-tagebuch"),
    ("auf-impuls", "farbe-impuls"),
    ("auf-eintraege", "farbe-eintraege"),
    ("auf-info", "farbe-info"),
    ("auf-start", "farbe-start"),
    ("auf-inhalte", "farbe-inhalte"),
    ("auf-zugaenge", "farbe-zugaenge"),
]


def _variablen(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", block))


def _bloecke() -> tuple[str, str]:
    hell = re.search(r"^:root \{(.*?)^\}", CSS, re.DOTALL | re.MULTILINE).group(1)
    dunkel = re.search(
        r"@media \(prefers-color-scheme: dark\) \{\s*:root \{(.*?)\}", CSS, re.DOTALL
    ).group(1)
    return hell, dunkel


def _schemata() -> dict[str, dict[str, str]]:
    hell, dunkel = _bloecke()
    return {"hell": _variablen(hell), "dunkel": {**_variablen(hell), **_variablen(dunkel)}}


def test_alle_farben_lesbar():
    """Jede Farbvariable steht als #rrggbb, sonst übersähe der Kontrasttest sie still."""
    keine_farben = ("radius", "pille", "sans", "schatten")
    for block in _bloecke():
        namen = set(re.findall(r"--([a-z0-9-]+):", block))
        farben = {n for n in namen if not n.startswith(keine_farben)}
        assert farben == set(_variablen(block)), farben - set(_variablen(block))


def _leuchtdichte(farbe: str) -> float:
    def kanal(wert: int) -> float:
        c = wert / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(farbe[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)


def kontrast(a: str, b: str) -> float:
    hell, dunkel = sorted((_leuchtdichte(a), _leuchtdichte(b)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)


def test_kontrast_rechnung():
    assert round(kontrast("#000000", "#ffffff"), 1) == 21.0
    assert round(kontrast("#777777", "#ffffff"), 2) == 4.48


@pytest.mark.parametrize("schema", ["hell", "dunkel"])
@pytest.mark.parametrize("schrift,grund", PAARE)
def test_kontrast_aa(schema, schrift, grund):
    farben = _schemata()[schema]
    wert = kontrast(farben[schrift], farben[grund])
    assert wert >= 4.5, f"{schema}: --{schrift} auf --{grund} nur {wert:.2f} : 1"
