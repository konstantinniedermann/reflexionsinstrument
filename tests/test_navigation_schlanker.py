"""Navigation ohne Übersicht, Abmelden zurückgenommen.

Siehe docs/superpowers/specs/2026-10-31-navigation-schlanker-design.md.
"""

import re

import pytest
from conftest import als_lehrperson, als_leitung, anmelden


def _kopf(text: str) -> str:
    return re.search(r'<header class="seitenkopf">.*?</header>', text, re.DOTALL).group(0)


def test_verwaltung_leitet_auf_inhalte(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    antwort = client.get("/verwaltung", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/verwaltung/inhalte"


def test_nach_anmeldung_direkt_inhalte(client, auftraggeberin):
    antwort = anmelden(client, auftraggeberin["benutzername"], auftraggeberin["passwort"])
    assert antwort.headers["location"] == "/verwaltung/inhalte"


def test_navigation_ohne_uebersicht(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    text = client.get("/verwaltung/inhalte").text
    nav = re.search(r'<nav class="verwaltungsnavigation".*?</nav>', text, re.DOTALL).group(0)
    namen = re.findall(r"<a [^>]*>([^<]*)</a>", nav)
    assert namen == ["Inhalte", "Einträge", "Vorschau", "Zugänge", "Benachrichtigung"]


@pytest.mark.parametrize(
    "pfad,satz",
    [
        ("/verwaltung/inhalte", "Hier legst du fest, was die Lehrpersonen im Instrument sehen"),
        ("/verwaltung/eintraege", "Hier liest du die Einträge der Lehrpersonen"),
        ("/verwaltung/vorschau", "So sieht es eine Lehrperson an einem bestimmten Tag"),
        ("/verwaltung/zugaenge", "Hier legst du Zugänge für Lehrpersonen an"),
        ("/verwaltung/benachrichtigung", "Hier schickst du eine kurze Erinnerung"),
    ],
)
def test_kurzbeschrieb_zuoberst(client, auftraggeberin, pfad, satz):
    """Direkt nach der Überschrift steht, wofür die Seite da ist."""
    als_leitung(client, auftraggeberin)
    text = client.get(pfad).text
    nach_h1 = re.search(r"</h1>\s*<p class=\"[^\"]*\">([^<]*)", text)
    assert nach_h1 and nach_h1.group(1).startswith(satz), pfad


def test_kein_abmelden_im_kopf(client, auftraggeberin, lehrperson):
    als_lehrperson(client, lehrperson)
    for pfad in ("/lehrperson", "/lehrperson/info", "/lehrperson/eintraege"):
        kopf = _kopf(client.get(pfad).text)
        assert "/abmelden" not in kopf, pfad
        assert "Anna Beispiel" in kopf, pfad
    client.cookies.clear()
    als_leitung(client, auftraggeberin)
    for pfad in ("/verwaltung/inhalte", "/verwaltung/zugaenge"):
        assert "/abmelden" not in _kopf(client.get(pfad).text), pfad


def test_abmelden_nur_auf_der_info_seite(client, lehrperson):
    als_lehrperson(client, lehrperson)
    assert 'action="/abmelden"' in client.get("/lehrperson/info").text
    for pfad in ("/lehrperson", "/lehrperson/eintraege", "/lehrperson/tagebuch/neu"):
        assert 'action="/abmelden"' not in client.get(pfad).text, pfad


@pytest.mark.parametrize(
    "pfad",
    [
        "/verwaltung/inhalte",
        "/verwaltung/eintraege",
        "/verwaltung/vorschau",
        "/verwaltung/zugaenge",
    ],
)
def test_abmelden_am_ende_der_verwaltung(client, auftraggeberin, pfad):
    als_leitung(client, auftraggeberin)
    text = client.get(pfad).text
    assert text.index('action="/abmelden"') > text.index("</main>")


def test_abmelden_wirkt_weiterhin(client, lehrperson):
    als_lehrperson(client, lehrperson)
    seite = client.get("/lehrperson/info").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', seite).group(1)
    antwort = client.post("/abmelden", data={"csrf": csrf}, follow_redirects=False)
    assert antwort.status_code == 303
    assert client.get("/lehrperson", follow_redirects=False).status_code == 303


def test_kein_abmelden_in_vorschau_und_gast(client, auftraggeberin, db):
    """Vorschau und Gast speichern nichts; Abmelden würde dort die Auftraggeberin abmelden."""
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')")
    db.commit()
    als_leitung(client, auftraggeberin)
    vorschau = client.get("/verwaltung/vorschau/2026-11-23/info")
    assert vorschau.status_code == 200
    assert 'action="/abmelden"' not in vorschau.text
    assert 'action="/abmelden"' not in client.get("/gast/info").text
