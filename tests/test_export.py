import csv
import io
from datetime import date

import pytest
from auswertung_daten import zeile

from app.export import SPALTEN, als_csv, exportzeilen, woche_von, zelle

START = date(2026, 11, 23)


def _lies(daten: bytes) -> list[list[str]]:
    text = daten.decode("utf-8")[1:]
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=";"))


def _tabelle(zeilen, projektstart=START, aufnahme=lambda z: ""):
    return _lies(als_csv(exportzeilen(zeilen, projektstart), aufnahme))


def _tagebuch(id_, tagebuch_art, frage, erstellt, art="tagebuch", **rest):
    return zeile(
        quelle="tagebuch",
        id=id_,
        art=art,
        tagebuch_art=tagebuch_art,
        angeleitet=False,
        runde_id=None,
        runde_titel=None,
        runde_freischaltdatum=None,
        frage_id=None,
        frage=frage,
        frage_typ=None,
        frage_reihenfolge=None,
        erstellt=erstellt,
        geaendert=erstellt,
        **rest,
    )


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [
        ("=SUMME(A1)", "'=SUMME(A1)"),
        ("+41 79", "'+41 79"),
        ("-1", "'-1"),
        ("- Punkt", "'- Punkt"),
        ("@x", "'@x"),
        ("\tx", "'\tx"),
        ("\rx", "'\nx"),
        ('=HYPERLINK("http://x")', '\'=HYPERLINK("http://x")'),
    ],
)
def test_zelle_formelzeichen(wert, erwartet):
    assert zelle(wert) == erwartet


def test_zelle_normal():
    assert zelle("Zoë «gut»") == "Zoë «gut»"
    assert zelle(None) == ""
    assert zelle(4) == "4"
    assert zelle("a\r\nb\rc") == "a\nb\nc"
    assert zelle("Text = gut") == "Text = gut"


def test_woche_von():
    assert woche_von("2026-11-22T23:30:00Z", START) == 1
    assert woche_von("2026-11-22T22:30:00Z", START) is None
    assert woche_von("2026-11-29T23:00:00Z", START) == 2
    assert woche_von("2026-11-24T08:00:00Z", None) is None


def test_exportzeilen_zeitzone():
    z = zeile(erstellt="2026-11-22T23:30:00Z", geaendert="2026-11-22T23:30:00Z")
    (e,) = exportzeilen([z], START)
    assert e.woche == 1
    assert "23.11.2026 00:30" in als_csv([e], lambda _: "").decode("utf-8")


def test_exportzeilen_sortierung():
    w2_anna = zeile(id=1, erstellt="2026-11-30T08:00:00Z")
    w1_ben = zeile(id=2, konto_id=2, anzeigename="Ben", erstellt="2026-11-24T08:00:00Z")
    w1_anna = zeile(id=3, erstellt="2026-11-25T08:00:00Z")
    vorher_ben = zeile(id=4, konto_id=2, anzeigename="Ben", erstellt="2026-11-10T08:00:00Z")
    ergebnis = exportzeilen([w2_anna, w1_ben, w1_anna, vorher_ben], START)
    assert [e.zeile.id for e in ergebnis] == [4, 3, 2, 1]
    ohne = exportzeilen([w1_ben, w2_anna], None)
    assert all(e.woche is None for e in ohne)
    assert [e.zeile.anzeigename for e in ohne] == ["Anna Beispiel", "Ben"]


def test_exportzeilen_gleicher_zeitpunkt_antworten():
    zweite = zeile(id=1, frage_reihenfolge=2)
    erste = zeile(id=2, frage_reihenfolge=1)
    assert [e.zeile.id for e in exportzeilen([zweite, erste], START)] == [2, 1]


def test_exportzeilen_gleicher_zeitpunkt_gemischt():
    antwort = zeile(id=1)
    eintrag = _tagebuch(1, "frei", None, antwort.erstellt)
    assert len(exportzeilen([eintrag, antwort], START)) == 2
    assert len(exportzeilen([antwort, eintrag], START)) == 2


def test_als_csv_format():
    wert = 'Er sagte "ja"; dann ging er. Zoë Müller\nZeile 2'
    daten = als_csv(
        exportzeilen([zeile(text=wert), zeile(id=2, text="Zeile 1\nZeile 2")], START),
        lambda _: "",
    )
    assert daten.startswith(b"\xef\xbb\xbf")
    zeilen = _lies(daten)
    assert zeilen[0] == list(SPALTEN)
    assert zeilen[1][SPALTEN.index("Antwort")] == wert
    assert zeilen[2][SPALTEN.index("Antwort")] == "Zeile 1\nZeile 2"
    # Kopf plus zwei Datensaetze; Umbrueche in Zellen sind nur "\n".
    assert daten.count(b"\r\n") == len(zeilen) == 3
    assert not daten.decode("utf-8")[1:].startswith("sep=")


def test_als_csv_keine_formel():
    tabelle = _tabelle([zeile(text="=1+1", anzeigename="@Anna")])
    for zelle_ in tabelle[1]:
        assert not zelle_.startswith(("=", "+", "-", "@"))
    assert tabelle[1][SPALTEN.index("Antwort")] == "'=1+1"


def test_als_csv_werte_pro_art():
    runde = zeile(
        id=1,
        frage="Frage B",
        frage_typ="skala",
        text=None,
        skalawert=4,
        aufnahme_id=None,
    )
    frei = _tagebuch(2, "frei", None, "2026-11-24T09:00:00Z", text="frei")
    leit = _tagebuch(3, "leitfragen", "Leitfrage X", "2026-11-24T10:00:00Z")
    impuls = _tagebuch(4, "impuls", "Impuls Y", "2026-11-24T11:00:00Z", art="impuls")
    gesprochen = _tagebuch(5, "aufnahme", None, "2026-11-24T12:00:00Z", text=None, aufnahme_id=7)
    t = _tabelle([runde, frei, leit, impuls, gesprochen], aufnahme=lambda z: f"auf{z.aufnahme_id}")
    s = SPALTEN.index
    assert t[1][s("Angeleitet oder freiwillig")] == "angeleitet"
    assert t[1][s("Art")] == "Runde"
    assert t[1][s("Runde")] == "Runde Eins"
    assert t[1][s("Frage")] == "Frage B"
    assert t[1][s("Antwort")] == ""
    assert t[1][s("Skalawert")] == "4"
    assert t[2][s("Angeleitet oder freiwillig")] == "freiwillig"
    assert t[2][s("Art")] == "Tagebuch"
    assert t[2][s("Runde")] == ""
    assert t[2][s("Frage")] == ""
    assert t[3][s("Frage")] == "Leitfrage X"
    assert t[4][s("Art")] == "Impuls"
    assert t[5][s("Antwort")] == ""
    assert t[5][s("Aufnahme")] == "auf7"


def test_als_csv_geaendert():
    s = SPALTEN.index("Geändert")
    assert _tabelle([zeile()])[1][s] == ""
    geaendert = zeile(geaendert="2026-11-25T09:15:00Z")
    assert _tabelle([geaendert])[1][s] == "25.11.2026 10:15"
