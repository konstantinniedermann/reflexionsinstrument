import re
from datetime import date

import pytest
from markupsafe import Markup

from app.formatierung import formatiere
from app.vorlagen import templates


def f(text):
    return str(formatiere(text))


def test_absaetze():
    assert f("Erster\n\nZweiter") == "<p>Erster</p><p>Zweiter</p>"
    assert f("Erster\n\n\n\nZweiter") == "<p>Erster</p><p>Zweiter</p>"


def test_zeilenumbruch():
    assert f("a\nb") == "<p>a<br>b</p>"


def test_crlf():
    assert f("a\r\nb\r\n\r\nc") == "<p>a<br>b</p><p>c</p>"


@pytest.mark.parametrize("text", ["- x", "* x", "• x", "-\tx", "•\tx", "  - x"])
def test_liste_zeichen(text):
    assert f(text) == "<ul><li>x</li></ul>"


def test_liste_nach_textzeile():
    assert f("Dazu gehört:\n- eins\n- zwei") == (
        "<p>Dazu gehört:</p><ul><li>eins</li><li>zwei</li></ul>"
    )


def test_text_nach_liste():
    assert f("- eins\nDanach") == "<ul><li>eins</li></ul><p>Danach</p>"


def test_kein_listenzeichen():
    assert f("-x") == "<p>-x</p>"
    assert f("**fett** am Anfang") == "<p><strong>fett</strong> am Anfang</p>"


def test_fett():
    assert f("Das ist **wichtig** hier") == "<p>Das ist <strong>wichtig</strong> hier</p>"
    assert f("- **a** b") == "<ul><li><strong>a</strong> b</li></ul>"


def test_einzelnes_sternpaar():
    assert f("a ** b") == "<p>a ** b</p>"
    assert f("** x **") == "<p>** x **</p>"


@pytest.mark.parametrize("text", [None, "", "  \n \n"])
def test_leer(text):
    assert formatiere(text) == Markup("")


def test_html_escapt():
    assert f("<script>alert(1)</script>") == "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"
    ausgabe = f('<img src=x onerror="a">')
    assert "&lt;img" in ausgabe and "&#34;" in ausgabe
    assert "&#39;" in f("Tom's")
    assert f("&amp;") == "<p>&amp;amp;</p>"
    assert f("**<b>x</b>**") == "<p><strong>&lt;b&gt;x&lt;/b&gt;</strong></p>"
    assert f("- <script>") == "<ul><li>&lt;script&gt;</li></ul>"


FEINDLICH = [
    "<script>alert(1)</script>",
    '<img src=x onerror="a">',
    "Tom's",
    "&amp;",
    "**<b>x</b>**",
    "- <script>",
    "**<img src=x onerror=alert(1)>**",
    "- **<a href=javascript:x>**",
    "<<p>>",
    "</p><script>",
    "* <svg/onload=alert(1)>\n\n<iframe>",
]


@pytest.mark.parametrize("text", FEINDLICH)
def test_feindliche_eingaben_ohne_fremde_tags(text):
    ausgabe = formatiere(text)
    assert isinstance(ausgabe, Markup)
    assert "<" not in re.sub(r"</?(p|br|ul|li|strong)>", "", ausgabe)


def test_filter_registriert():
    filters = templates.env.filters
    assert filters["formatiert"]("**a**") == Markup("<p><strong>a</strong></p>")
    assert filters["datum"]("2026-11-30") == "Mo 30.11.2026"
    assert filters["datum"](date(2026, 11, 30), mit_jahr=False) == "Mo 30.11."
    assert templates.env.globals["zeitplan"]


@pytest.mark.parametrize("wert", [None, ""])
def test_datumsfilter_ohne_datum(wert):
    assert templates.env.filters["datum"](wert) == ""
