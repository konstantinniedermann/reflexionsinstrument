import testdaten

from app.eintraege import alle_zeilen, gruppiere, zeilen_von

T = "2026-11-23T{}:00:00Z"


def _zeit_antwort(db, antwort_id, erstellt, geaendert=None):
    db.execute(
        "UPDATE antworten SET erstellt = ?, geaendert = ? WHERE id = ?",
        (erstellt, geaendert or erstellt, antwort_id),
    )


def _zeit_eintrag(db, eintrag_id, erstellt):
    db.execute(
        "UPDATE tagebucheintraege SET erstellt = ?, geaendert = ? WHERE id = ?",
        (erstellt, erstellt, eintrag_id),
    )


def test_alle_zeilen_werte(db, lehrperson, zweite_lehrperson, einstellungen):
    konto = lehrperson["id"]
    verzeichnis = einstellungen.daten_verzeichnis / "aufnahmen"
    rid, (f1, f2) = testdaten.lege_runde_an(db, titel="Runde 1")
    rid2, (g1, _) = testdaten.lege_runde_an(db, titel="Spaeter", freischaltdatum="2099-01-01")
    aid = testdaten.lege_aufnahme_an(db, konto, verzeichnis)
    a_text = testdaten.lege_antwort_an(db, f1, konto, "Text")
    a_skala = testdaten.lege_antwort_an(db, f2, konto, None, 4)
    a_aufn = testdaten.lege_antwort_an(db, g1, konto, None, aufnahme_id=aid)
    impuls = testdaten.lege_impuls_an(db, "Impuls A")
    leitfrage = testdaten.lege_leitfrage_an(db, "Leitfrage A")
    t_frei = testdaten.lege_eintrag_an(db, konto, "frei", "frei")
    t_leit = testdaten.lege_eintrag_an(db, konto, "leitfragen", "leit", leitfrage_id=leitfrage)
    t_imp = testdaten.lege_eintrag_an(db, konto, "impuls", "imp", impuls_id=impuls)
    aid2 = testdaten.lege_aufnahme_an(db, konto, verzeichnis, dauer_sekunden=5)
    t_aufn = testdaten.lege_eintrag_an(db, konto, "aufnahme", None, aufnahme_id=aid2)
    testdaten.lege_eintrag_an(db, zweite_lehrperson["id"], "frei", "fremd")

    zeilen = alle_zeilen(db)
    assert len(zeilen) == 8
    nach = {(z.quelle, z.id): z for z in zeilen}

    z = nach["antwort", a_text]
    assert (z.art, z.angeleitet, z.tagebuch_art, z.frage, z.text, z.skalawert) == (
        "runde", True, None, "Frage A", "Text", None,
    )  # fmt: skip
    assert (z.runde_id, z.runde_titel, z.frage_id) == (rid, "Runde 1", f1)
    assert (z.frage_typ, z.frage_reihenfolge, z.anzeigename) == ("freitext", 1, "Anna Beispiel")
    assert z.aufnahme_dateiname is None

    z = nach["antwort", a_skala]
    assert (z.skalawert, z.text, z.frage, z.frage_typ) == (4, None, "Frage B", "skala")

    z = nach["antwort", a_aufn]
    assert z.runde_id == rid2 and z.runde_freischaltdatum == "2099-01-01"
    assert z.aufnahme_id == aid and z.aufnahme_mime_typ == "audio/webm"
    assert z.aufnahme_dateiname.endswith(".webm") and z.aufnahme_dauer_sekunden == 5

    z = nach["tagebuch", t_frei]
    assert (z.art, z.tagebuch_art, z.angeleitet, z.frage) == ("tagebuch", "frei", False, None)
    assert z.runde_id is z.frage_id is z.frage_typ is z.frage_reihenfolge is None
    z = nach["tagebuch", t_leit]
    assert (z.art, z.tagebuch_art, z.frage) == ("tagebuch", "leitfragen", "Leitfrage A")
    z = nach["tagebuch", t_imp]
    assert (z.art, z.tagebuch_art, z.frage, z.angeleitet) == ("impuls", "impuls", "Impuls A", False)
    z = nach["tagebuch", t_aufn]
    assert (z.art, z.tagebuch_art, z.text, z.aufnahme_dauer_sekunden) == (
        "tagebuch", "aufnahme", None, 5,
    )  # fmt: skip
    assert z.anzeigename == "Anna Beispiel"


def test_zeilen_von_nur_eigenes(db, lehrperson, zweite_lehrperson):
    _, (f1, _) = testdaten.lege_runde_an(db)
    testdaten.lege_antwort_an(db, f1, lehrperson["id"])
    testdaten.lege_antwort_an(db, f1, zweite_lehrperson["id"])
    testdaten.lege_eintrag_an(db, zweite_lehrperson["id"])
    zeilen = zeilen_von(db, lehrperson["id"])
    assert len(zeilen) == 1
    assert {z.konto_id for z in zeilen} == {lehrperson["id"]}
    assert len(zeilen_von(db, zweite_lehrperson["id"])) == 2


def test_zeilen_sortiert(db, lehrperson):
    konto = lehrperson["id"]
    _, (f1, _f2) = testdaten.lege_runde_an(db)
    a1 = testdaten.lege_antwort_an(db, f1, konto)
    t1 = testdaten.lege_eintrag_an(db, konto)
    t2 = testdaten.lege_eintrag_an(db, konto)
    _zeit_antwort(db, a1, T.format("10"))
    _zeit_eintrag(db, t1, T.format("10"))
    _zeit_eintrag(db, t2, T.format("09"))
    assert [(z.quelle, z.id) for z in zeilen_von(db, konto)] == [
        ("tagebuch", t2),
        ("antwort", a1),
        ("tagebuch", t1),
    ]


def test_gruppiere(db, lehrperson, zweite_lehrperson):
    konto = lehrperson["id"]
    rid, (f1, f2) = testdaten.lege_runde_an(db)
    a2 = testdaten.lege_antwort_an(db, f2, konto, None, 3)
    a1 = testdaten.lege_antwort_an(db, f1, konto)
    _zeit_antwort(db, a2, T.format("09"), T.format("12"))
    _zeit_antwort(db, a1, T.format("08"))
    t = testdaten.lege_eintrag_an(db, konto)
    _zeit_eintrag(db, t, T.format("10"))

    karten = gruppiere(zeilen_von(db, konto))
    assert [k.art for k in karten] == ["tagebuch", "runde"]
    tagebuch, runde = karten
    assert (tagebuch.eintrag_id, tagebuch.runde_id) == (t, None)
    assert len(tagebuch.zeilen) == 1
    assert (runde.runde_id, runde.eintrag_id) == (rid, None)
    assert (runde.erstellt, runde.geaendert) == (T.format("08"), T.format("12"))
    assert [z.frage_id for z in runde.zeilen] == [f1, f2]
    assert runde.anzeigename == "Anna Beispiel"


def test_gruppiere_gleichstand(db, lehrperson):
    konto = lehrperson["id"]
    rid, (f1, _) = testdaten.lege_runde_an(db)
    a = testdaten.lege_antwort_an(db, f1, konto)
    t1 = testdaten.lege_eintrag_an(db, konto)
    t2 = testdaten.lege_eintrag_an(db, konto)
    _zeit_antwort(db, a, T.format("08"))
    _zeit_eintrag(db, t1, T.format("08"))
    _zeit_eintrag(db, t2, T.format("08"))
    karten = gruppiere(alle_zeilen(db))
    assert [(k.art, k.eintrag_id, k.runde_id) for k in karten] == [
        ("tagebuch", t2, None),
        ("tagebuch", t1, None),
        ("runde", None, rid),
    ]


def test_gruppiere_zwei_lehrpersonen_eine_runde(db, lehrperson, zweite_lehrperson):
    _, (f1, _) = testdaten.lege_runde_an(db)
    testdaten.lege_antwort_an(db, f1, lehrperson["id"])
    testdaten.lege_antwort_an(db, f1, zweite_lehrperson["id"])
    karten = gruppiere(alle_zeilen(db))
    assert len(karten) == 2
    assert {k.konto_id for k in karten} == {lehrperson["id"], zweite_lehrperson["id"]}


def test_fremde_aufnahme_nicht_in_zeilen(db, lehrperson, zweite_lehrperson, einstellungen):
    konto = lehrperson["id"]
    verzeichnis = einstellungen.daten_verzeichnis / "aufnahmen"
    fremd = testdaten.lege_aufnahme_an(db, zweite_lehrperson["id"], verzeichnis, dauer_sekunden=5)
    _, (f1, _) = testdaten.lege_runde_an(db)
    testdaten.lege_antwort_an(db, f1, konto, "Text", aufnahme_id=fremd)
    testdaten.lege_eintrag_an(db, konto, "aufnahme", None, aufnahme_id=fremd)
    zeilen = zeilen_von(db, konto)
    assert len(zeilen) == 2
    for z in zeilen:
        assert z.aufnahme_id == fremd
        assert (z.aufnahme_dateiname, z.aufnahme_mime_typ, z.aufnahme_dauer_sekunden) == (
            None,
            None,
            None,
        )
