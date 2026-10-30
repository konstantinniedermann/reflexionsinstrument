import sqlite3
from datetime import date

import pytest
from testdaten import lege_antwort_an, lege_eintrag_an

from app import inhalte
from app.db import transaktion
from app.eingaben import Gesperrt, InhaltFehler, kurzer_text
from app.inhalte import (
    NichtGefunden,
    aendere_frage,
    aendere_impuls,
    aendere_info,
    aendere_leitfrage,
    aendere_runde,
    datum_vorschlag_impuls,
    datum_vorschlag_runde,
    frage,
    fragen,
    impuls,
    impulse,
    info_abschnitt,
    info_abschnitte,
    lege_frage_an,
    lege_impuls_an,
    lege_info_an,
    lege_leitfrage_an,
    lege_runde_an,
    leitfrage,
    leitfragen,
    lies_projektstart,
    lies_titel,
    loesche_frage,
    loesche_impuls,
    loesche_info,
    loesche_leitfrage,
    loesche_runde,
    runde,
    runden,
    speichere_allgemein,
    verschiebe,
    zaehle_antworten_frage,
    zaehle_antworten_runde,
    zaehle_inhalte,
)
from app.texte import lies_text


def test_kurzer_text_wird_eine_zeile():
    assert kurzer_text("a\r\nb\nc ", "f", 500, "m") == "a b c"
    assert kurzer_text("", "f", 60, None) is None


def test_titel_standard(db):
    assert lies_titel(db) == "Reflexionsinstrument"
    assert lies_projektstart(db) is None


def test_speichere_allgemein(db):
    speichere_allgemein(db, "Lernheft", "Hallo **alle**", "2026-11-23")
    assert lies_titel(db) == "Lernheft"
    assert lies_text(db, "begruessung") == "Hallo **alle**"
    assert lies_projektstart(db) == date(2026, 11, 23)


def test_allgemein_ohne_ersten_tag(db):
    speichere_allgemein(db, "Lernheft", "Hallo", "2026-11-23")
    speichere_allgemein(db, "Lernheft", "Hallo", "")
    assert lies_projektstart(db) is None


def test_allgemein_fehler_schreibt_nichts(db):
    speichere_allgemein(db, "Alt", "Alter Text", "2026-11-23")
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, "Neu", "Neuer Text", "23.11.2026")
    assert e.value.feld == "projektstart"
    assert lies_titel(db) == "Alt"
    assert lies_text(db, "begruessung") == "Alter Text"
    assert lies_projektstart(db) == date(2026, 11, 23)


def test_titel_zu_lang(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, "x" * 61, "Hallo", "")
    assert e.value.feld == "titel"


def test_titel_leer(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, " ", "Hallo", "")
    assert e.value.feld == "titel"


def test_begruessung_leer(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, "Titel", " ", "")
    assert e.value.feld == "begruessung"


def test_transaktion_verschachtelt(db):
    with pytest.raises(RuntimeError), transaktion(db):
        speichere_allgemein(db, "Neu", "Neuer Text", "2026-11-23")
        raise RuntimeError("abbruch")
    assert lies_titel(db) == "Reflexionsinstrument"
    assert lies_projektstart(db) is None
    assert not db.in_transaction


def test_zaehle_inhalte(db):
    db.execute("INSERT INTO runden (titel, freischaltdatum) VALUES ('A', '2026-11-23')")
    db.execute("INSERT INTO runden (titel, freischaltdatum) VALUES ('B', '2026-11-30')")
    for i in range(3):
        db.execute(f"INSERT INTO fragen (runde_id, typ, text) VALUES (1, 'freitext', 'F{i}')")
    db.execute("INSERT INTO info_abschnitte (titel, inhalt) VALUES ('T', 'I')")
    assert zaehle_inhalte(db) == {
        "runden": 2,
        "fragen": 3,
        "runden_ohne_fragen": 1,
        "info_abschnitte": 1,
        "leitfragen": 0,
        "impulse": 0,
    }


# ---------- Runden und Fragen ----------


def _konto(db, name="k1"):
    return db.execute(
        "INSERT INTO konten (anzeigename, benutzername, passwort_hash, rolle) "
        "VALUES (?, ?, 'x', 'lehrperson')",
        (name, name),
    ).lastrowid


def _runde(db, datum="2026-11-23", titel="Runde"):
    return lege_runde_an(db, titel, "", datum)


def _frage(db, rid, text="Frage", typ="freitext"):
    mn, mx = ("eins", "fuenf") if typ == "skala" else ("", "")
    return lege_frage_an(db, rid, typ, text, mn, mx)


def _texte(db, rid):
    return [f["text"] for f in fragen(db, rid)]


def test_runden_nach_datum_sortiert(db):
    a = _runde(db, "2026-12-07", "a")
    b = _runde(db, "2026-11-23", "b")
    c = _runde(db, "2026-11-23", "c")
    assert [r["id"] for r in runden(db)] == [b, c, a]


def test_datum_vorschlag_runde(db):
    assert datum_vorschlag_runde(db) is None
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')")
    assert datum_vorschlag_runde(db) == date(2026, 11, 23)
    _runde(db, "2026-11-30")
    assert datum_vorschlag_runde(db) == date(2026, 12, 7)


def test_datum_vorschlag_runde_ohne_start_mit_runde(db):
    _runde(db, "2026-11-30")
    assert datum_vorschlag_runde(db) == date(2026, 12, 7)


def test_runde_fallbeispiel_leer_ist_null(db):
    rid = lege_runde_an(db, "T", "  \n ", "2026-11-23")
    assert runde(db, rid)["fallbeispiel"] is None
    aendere_runde(db, rid, "T", "Text", "2026-11-23")
    assert runde(db, rid)["fallbeispiel"] == "Text"
    aendere_runde(db, rid, "T", "", "2026-11-23")
    assert runde(db, rid)["fallbeispiel"] is None


def test_runde_ungueltig(db):
    with pytest.raises(InhaltFehler) as fehler:
        lege_runde_an(db, "", "", "2026-11-23")
    assert fehler.value.feld == "titel"
    with pytest.raises(InhaltFehler) as fehler:
        lege_runde_an(db, "T", "", "")
    assert fehler.value.feld == "freischaltdatum"
    assert fehler.value.meldung == "Bitte ein Datum wählen."
    with pytest.raises(InhaltFehler) as fehler:
        lege_runde_an(db, "x" * 101, "", "2026-11-23")
    assert fehler.value.feld == "titel"
    assert runden(db) == []


def test_runde_anzahl_fragen(db):
    rid = _runde(db)
    _frage(db, rid)
    _frage(db, rid)
    assert runde(db, rid)["anzahl_fragen"] == 2
    assert runde(db, 999) is None


def test_frage_anlegen_am_ende(db):
    rid = _runde(db)
    for t in "abc":
        _frage(db, rid, t)
    assert [f["reihenfolge"] for f in fragen(db, rid)] == [1, 2, 3]


def test_freitext_speichert_keine_beschriftungen(db):
    rid = _runde(db)
    fid = lege_frage_an(db, rid, "freitext", "F", "eins", "fuenf")
    f = frage(db, fid)
    assert f["skala_min_text"] is None and f["skala_max_text"] is None


def test_skala_braucht_beschriftungen(db):
    rid = _runde(db)
    with pytest.raises(InhaltFehler) as fehler:
        lege_frage_an(db, rid, "skala", "F", "", "viel")
    assert fehler.value.feld == "skala_min_text"
    assert fehler.value.meldung == "Für die Skala braucht es beide Beschriftungen."
    with pytest.raises(InhaltFehler) as fehler:
        lege_frage_an(db, rid, "skala", "F", "wenig", " ")
    assert fehler.value.feld == "skala_max_text"
    with pytest.raises(InhaltFehler) as fehler:
        lege_frage_an(db, rid, "skala", "F", "x" * 61, "viel")
    assert fehler.value.feld == "skala_min_text"
    assert fragen(db, rid) == []


def test_unbekannte_art(db):
    rid = _runde(db)
    with pytest.raises(InhaltFehler) as fehler:
        lege_frage_an(db, rid, "auswahl", "F", "", "")
    assert fehler.value.feld == "typ"
    with pytest.raises(InhaltFehler) as fehler:
        lege_frage_an(db, rid, "freitext", "", "", "")
    assert fehler.value.feld == "text"
    assert fehler.value.meldung == "Bitte eine Frage eingeben."


def test_verschiebe_frage(db):
    r1, r2 = _runde(db), _runde(db, "2026-11-30")
    a, b, c = (_frage(db, r1, t) for t in "abc")
    _frage(db, r2, "x")
    _frage(db, r2, "y")
    verschiebe(db, "frage", c, "hoch")
    assert _texte(db, r1) == ["a", "c", "b"]
    assert [f["reihenfolge"] for f in fragen(db, r1)] == [1, 2, 3]
    verschiebe(db, "frage", a, "hoch")
    verschiebe(db, "frage", b, "runter")
    assert _texte(db, r1) == ["a", "c", "b"]
    assert _texte(db, r2) == ["x", "y"]
    assert [f["reihenfolge"] for f in fragen(db, r2)] == [1, 2]
    with pytest.raises(ValueError):
        verschiebe(db, "frage", a, "seitlich")
    with pytest.raises(ValueError):
        verschiebe(db, "unbekannt", a, "hoch")


def test_verschiebe_repariert_reihenfolge(db):
    rid = _runde(db)
    ids = [_frage(db, rid, t) for t in "abc"]
    for fid, wert in zip(ids, (0, 0, 5)):
        db.execute("UPDATE fragen SET reihenfolge = ? WHERE id = ?", (wert, fid))
    verschiebe(db, "frage", ids[0], "hoch")
    assert [f["reihenfolge"] for f in fragen(db, rid)] == [1, 2, 3]
    assert _texte(db, rid) == ["a", "b", "c"]


def test_verschiebe_unbekannter_eintrag_wirft_nicht(db):
    rid = _runde(db)
    _frage(db, rid)
    verschiebe(db, "frage", 999, "hoch")
    assert len(fragen(db, rid)) == 1


def test_loeschen_nummeriert_neu(db):
    rid = _runde(db)
    _frage(db, rid, "a")
    mitte = _frage(db, rid, "b")
    _frage(db, rid, "c")
    loesche_frage(db, mitte)
    assert [(f["text"], f["reihenfolge"]) for f in fragen(db, rid)] == [("a", 1), ("c", 2)]


def test_frage_mit_antworten_text_aendern(db):
    rid = _runde(db)
    fid = _frage(db, rid, "alt", "skala")
    k1, k2 = _konto(db, "a"), _konto(db, "b")
    db.execute("INSERT INTO antworten (frage_id, konto_id, skalawert) VALUES (?, ?, 4)", (fid, k1))
    lege_antwort_an(db, fid, k2, "Text")
    vorher = [tuple(z) for z in db.execute("SELECT * FROM antworten ORDER BY id")]
    aendere_frage(db, fid, "skala", "neu", "wenig", "viel")
    nachher = [tuple(z) for z in db.execute("SELECT * FROM antworten ORDER BY id")]
    assert vorher == nachher and len(vorher) == 2
    f = frage(db, fid)
    assert (f["text"], f["skala_min_text"], f["skala_max_text"]) == ("neu", "wenig", "viel")
    assert f["anzahl_antworten"] == 2


def test_frage_mit_antworten_art_aendern_verboten(db):
    rid = _runde(db)
    fid = _frage(db, rid, "alt")
    lege_antwort_an(db, fid, _konto(db))
    antworten = [tuple(z) for z in db.execute("SELECT * FROM antworten")]
    with pytest.raises(InhaltFehler) as fehler:
        aendere_frage(db, fid, "skala", "neu", "a", "b")
    assert fehler.value.feld == "typ"
    assert "lässt sich nicht mehr ändern" in fehler.value.meldung
    f = frage(db, fid)
    assert (f["typ"], f["text"], f["skala_min_text"]) == ("freitext", "alt", None)
    assert [tuple(z) for z in db.execute("SELECT * FROM antworten")] == antworten


def test_frage_ohne_antworten_art_aendern_erlaubt(db):
    rid = _runde(db)
    fid = _frage(db, rid)
    aendere_frage(db, fid, "skala", "F", "a", "b")
    assert frage(db, fid)["typ"] == "skala"


def test_frage_mit_antworten_loeschen_gesperrt(db):
    rid = _runde(db)
    fid = _frage(db, rid)
    lege_antwort_an(db, fid, _konto(db, "a"))
    lege_antwort_an(db, fid, _konto(db, "b"))
    with pytest.raises(Gesperrt) as gesperrt:
        loesche_frage(db, fid)
    assert gesperrt.value.anzahl == 2
    assert frage(db, fid) is not None
    assert zaehle_antworten_frage(db, fid) == 2


def test_antwort_nur_aufnahme_sperrt(db):
    rid = _runde(db)
    fid = _frage(db, rid)
    konto = _konto(db)
    aufnahme = db.execute(
        "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes) "
        "VALUES (?, 'a.webm', 'audio/webm', 10)",
        (konto,),
    ).lastrowid
    lege_antwort_an(db, fid, konto, text=None, aufnahme_id=aufnahme)
    with pytest.raises(Gesperrt):
        loesche_frage(db, fid)
    assert zaehle_antworten_runde(db, rid) == 1


def test_runde_mit_antworten_loeschen_gesperrt(db):
    rid = _runde(db)
    _frage(db, rid, "a")
    lege_antwort_an(db, _frage(db, rid, "b"), _konto(db))
    with pytest.raises(Gesperrt) as gesperrt:
        loesche_runde(db, rid)
    assert gesperrt.value.anzahl == 1
    assert runde(db, rid) is not None
    assert len(fragen(db, rid)) == 2
    assert zaehle_antworten_runde(db, rid) == 1


def test_runde_ohne_antworten_loeschen(db):
    rid = _runde(db)
    _frage(db, rid)
    _frage(db, rid)
    assert loesche_runde(db, rid) == 2
    assert runde(db, rid) is None
    assert db.execute("SELECT COUNT(*) FROM fragen").fetchone()[0] == 0


def test_sicherheitsnetz_integrity_error(db, monkeypatch):
    rid = _runde(db)
    fid = _frage(db, rid)
    lege_antwort_an(db, fid, _konto(db))
    monkeypatch.setattr(inhalte, "zaehle_antworten_frage", lambda db, frage_id: 0)
    with pytest.raises(Gesperrt):
        loesche_frage(db, fid)
    assert frage(db, fid) is not None
    assert db.execute("SELECT COUNT(*) FROM antworten").fetchone()[0] == 1
    assert not db.in_transaction


def test_sicherheitsnetz_runde(db, monkeypatch):
    rid = _runde(db)
    fid = _frage(db, rid)
    lege_antwort_an(db, fid, _konto(db))
    monkeypatch.setattr(inhalte, "zaehle_antworten_runde", lambda db, runde_id: 0)
    with pytest.raises(Gesperrt):
        loesche_runde(db, rid)
    assert runde(db, rid) is not None and frage(db, fid) is not None


def test_frage_in_fehlende_runde_ist_nicht_gefunden(db):
    with pytest.raises(NichtGefunden):
        lege_frage_an(db, 999, "freitext", "Frage", "", "")


def test_andere_integrity_error_bleibt_bestehen(db, monkeypatch):
    rid = _runde(db)
    monkeypatch.setattr(inhalte, "runde", lambda db, runde_id: {"id": runde_id})
    with pytest.raises(sqlite3.IntegrityError):
        lege_frage_an(db, 999, "freitext", "Frage", "", "")
    assert rid


# ---------- Infoblock und Leitfragen ----------


def _titel_info(db):
    return [a["titel"] for a in info_abschnitte(db)]


def test_info_anlegen_am_ende(db):
    a = lege_info_an(db, "Eins", "Text eins")
    b = lege_info_an(db, " Zwei ", "Text\r\nzwei ")
    assert _titel_info(db) == ["Eins", "Zwei"]
    assert info_abschnitt(db, b)["inhalt"] == "Text\nzwei"
    assert [info_abschnitt(db, i)["reihenfolge"] for i in (a, b)] == [1, 2]
    assert info_abschnitt(db, 999) is None


def test_info_ungueltig(db):
    with pytest.raises(InhaltFehler) as fehler:
        lege_info_an(db, "  ", "Text")
    assert (fehler.value.feld, fehler.value.meldung) == ("titel", "Bitte einen Titel eingeben.")
    with pytest.raises(InhaltFehler) as fehler:
        lege_info_an(db, "Titel", "")
    assert (fehler.value.feld, fehler.value.meldung) == ("inhalt", "Bitte einen Text eingeben.")
    with pytest.raises(InhaltFehler) as fehler:
        lege_info_an(db, "Titel", "x" * 20_001)
    assert fehler.value.feld == "inhalt"
    with pytest.raises(InhaltFehler):
        lege_info_an(db, "t" * 101, "Text")
    assert info_abschnitte(db) == []
    aid = lege_info_an(db, "Titel", "Text")
    with pytest.raises(InhaltFehler):
        aendere_info(db, aid, "", "Text")
    assert info_abschnitt(db, aid)["titel"] == "Titel"


def test_info_aendern_und_unbekannt(db):
    aid = lege_info_an(db, "Alt", "Alt")
    aendere_info(db, aid, "Neu", "Neuer Text")
    assert (info_abschnitt(db, aid)["titel"], info_abschnitt(db, aid)["inhalt"]) == (
        "Neu",
        "Neuer Text",
    )
    with pytest.raises(NichtGefunden):
        aendere_info(db, 999, "a", "b")
    with pytest.raises(NichtGefunden):
        loesche_info(db, 999)


def test_info_loeschen_nummeriert_neu(db):
    a = lege_info_an(db, "A", "a")
    b = lege_info_an(db, "B", "b")
    c = lege_info_an(db, "C", "c")
    loesche_info(db, b)
    assert _titel_info(db) == ["A", "C"]
    assert [info_abschnitt(db, i)["reihenfolge"] for i in (a, c)] == [1, 2]


def test_info_verschieben(db):
    a = lege_info_an(db, "A", "a")
    lege_info_an(db, "B", "b")
    verschiebe(db, "info", a, "runter")
    assert _titel_info(db) == ["B", "A"]


def test_leitfrage_eine_zeile(db):
    lid = lege_leitfrage_an(db, "a\nb")
    assert leitfrage(db, lid)["text"] == "a b"
    with pytest.raises(InhaltFehler) as fehler:
        lege_leitfrage_an(db, " ")
    assert fehler.value.meldung == "Bitte eine Leitfrage eingeben."
    with pytest.raises(InhaltFehler):
        lege_leitfrage_an(db, "x" * 501)
    assert [x["text"] for x in leitfragen(db)] == ["a b"]


def test_leitfragen_am_ende_und_neu_nummeriert(db):
    a = lege_leitfrage_an(db, "A")
    b = lege_leitfrage_an(db, "B")
    c = lege_leitfrage_an(db, "C")
    assert [x["text"] for x in leitfragen(db)] == ["A", "B", "C"]
    loesche_leitfrage(db, a)
    assert [leitfrage(db, i)["reihenfolge"] for i in (b, c)] == [1, 2]
    with pytest.raises(NichtGefunden):
        aendere_leitfrage(db, 999, "x")
    with pytest.raises(NichtGefunden):
        loesche_leitfrage(db, 999)


def test_leitfrage_mit_eintrag_aendern(db):
    lid = lege_leitfrage_an(db, "Alt")
    eid = lege_eintrag_an(db, _konto(db), art="leitfragen", leitfrage_id=lid)
    assert leitfrage(db, lid)["anzahl_eintraege"] == 1
    aendere_leitfrage(db, lid, "Neu")
    zeile = db.execute("SELECT * FROM tagebucheintraege WHERE id = ?", (eid,)).fetchone()
    assert zeile["leitfrage_text"] == "Alt"
    assert zeile["leitfrage_id"] == lid
    assert leitfrage(db, lid)["text"] == "Neu"


def test_leitfrage_mit_eintrag_loeschen(db):
    lid = lege_leitfrage_an(db, "Alt")
    eid = lege_eintrag_an(db, _konto(db), art="leitfragen", leitfrage_id=lid)
    loesche_leitfrage(db, lid)
    zeile = db.execute("SELECT * FROM tagebucheintraege WHERE id = ?", (eid,)).fetchone()
    assert zeile["leitfrage_id"] is None
    assert zeile["leitfrage_text"] == "Alt"
    assert leitfragen(db) == []


# ---------- Impulse ----------


def test_impulse_nach_datum(db):
    a = lege_impuls_an(db, "A", "2026-12-07")
    b = lege_impuls_an(db, "B", "2026-11-23")
    c = lege_impuls_an(db, "C", "2026-11-23")
    assert [i["id"] for i in impulse(db)] == [b, c, a]
    assert impuls(db, a)["anzahl_eintraege"] == 0
    assert impuls(db, 999) is None


def test_datum_vorschlag_impuls(db):
    assert datum_vorschlag_impuls(db) is None
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')")
    assert datum_vorschlag_impuls(db) == date(2026, 11, 23)
    lege_impuls_an(db, "A", "2026-11-30")
    assert datum_vorschlag_impuls(db) == date(2026, 12, 7)


def test_impuls_ungueltig(db):
    with pytest.raises(InhaltFehler) as fehler:
        lege_impuls_an(db, " ", "2026-11-23")
    assert (fehler.value.feld, fehler.value.meldung) == ("text", "Bitte einen Impuls eingeben.")
    with pytest.raises(InhaltFehler) as fehler:
        lege_impuls_an(db, "x" * 501, "2026-11-23")
    assert fehler.value.feld == "text"
    for datum in ("2026-11-31", ""):
        with pytest.raises(InhaltFehler) as fehler:
            lege_impuls_an(db, "Text", datum)
        assert fehler.value.feld == "sichtbar_ab"
    iid = lege_impuls_an(db, "a\nb", "2026-11-23")
    assert impuls(db, iid)["text"] == "a b"
    with pytest.raises(InhaltFehler):
        aendere_impuls(db, iid, "", "2026-11-23")
    with pytest.raises(NichtGefunden):
        aendere_impuls(db, 999, "x", "2026-11-23")
    with pytest.raises(NichtGefunden):
        loesche_impuls(db, 999)


def test_impuls_mit_eintrag_aendern_und_loeschen(db):
    iid = lege_impuls_an(db, "Alt", "2026-11-23")
    eid = lege_eintrag_an(db, _konto(db), art="impuls", impuls_id=iid)
    assert impuls(db, iid)["anzahl_eintraege"] == 1
    aendere_impuls(db, iid, "Neu", "2026-11-30")
    zeile = db.execute("SELECT * FROM tagebucheintraege WHERE id = ?", (eid,)).fetchone()
    assert (zeile["impuls_text"], zeile["impuls_id"]) == ("Alt", iid)
    assert impuls(db, iid)["text"] == "Neu"
    loesche_impuls(db, iid)
    zeile = db.execute("SELECT * FROM tagebucheintraege WHERE id = ?", (eid,)).fetchone()
    assert zeile["impuls_id"] is None
    assert zeile["impuls_text"] == "Alt"
    assert impulse(db) == []


@pytest.mark.parametrize("datum", ["0026-11-23", "9999-12-31", "2019-12-31", "2100-01-01"])
def test_unplausibles_datum_abgelehnt(db, datum):
    with pytest.raises(InhaltFehler) as fehler:
        lege_runde_an(db, "T", "", datum)
    assert fehler.value.meldung == "Bitte ein Datum zwischen 2020 und 2099 wählen."
    with pytest.raises(InhaltFehler):
        lege_impuls_an(db, "T", datum)
    assert runden(db) == [] and impulse(db) == []


def test_datum_grenzen_erlaubt(db):
    lege_runde_an(db, "A", "", "2020-01-01")
    lege_runde_an(db, "B", "", "2099-12-31")
    assert len(runden(db)) == 2


def test_datum_vorschlag_mit_altwert_ohne_absturz(db):
    db.execute("INSERT INTO runden (titel, freischaltdatum) VALUES ('X', '9999-12-31')")
    db.execute("INSERT INTO impulse (text, sichtbar_ab) VALUES ('X', '9999-12-31')")
    assert datum_vorschlag_runde(db) is None
    assert datum_vorschlag_impuls(db) is None
