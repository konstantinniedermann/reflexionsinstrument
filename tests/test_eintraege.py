import pytest
import testdaten

from app.aufnahmen import aufnahmen_von_eintraegen
from app.db import transaktion
from app.eingaben import InhaltFehler
from app.eintraege import (
    Stand,
    antworten_der_runde,
    lies_runden_eingaben,
    loesche_antworten_der_runde,
    rundenstand,
    speichere_antworten,
)
from app.inhalte import fragen as lade_fragen

T1 = "2026-11-23T10:00:00Z"
T2 = "2026-11-23T11:00:00Z"
T3 = "2026-11-23T12:00:00Z"


@pytest.fixture
def runde(db):
    rid, (f1, f2) = testdaten.lege_runde_an(db)
    return rid, f1, f2, lade_fragen(db, rid)


def test_eingaben_normalisiert(runde):
    _, f1, f2, fragen = runde
    assert lies_runden_eingaben(fragen, {f"antwort_{f1}": "  a\r\nb ", f"antwort_{f2}": "4"}) == {
        f1: ("a\nb", None),
        f2: (None, 4),
    }
    assert lies_runden_eingaben(fragen, {f"antwort_{f1}": "", f"antwort_{f2}": ""}) == {
        f1: (None, None),
        f2: (None, None),
    }


def test_fehlendes_feld_bleibt_unberuehrt(db, lehrperson, runde):
    rid, f1, f2, fragen = runde
    testdaten.lege_antwort_an(db, f2, lehrperson["id"], text=None, skalawert=3)
    eingaben = lies_runden_eingaben(fragen, {f"antwort_{f1}": "x"})
    assert f2 not in eingaben
    speichere_antworten(db, lehrperson["id"], eingaben)
    assert antworten_der_runde(db, lehrperson["id"], rid)[f2]["skalawert"] == 3


@pytest.mark.parametrize("wert", ["0", "6", "x", "3.0", " 3", "+3", "٣", "0" * 5000 + "3", "03"])
def test_skala_ungueltig(runde, wert):
    _, _, f2, fragen = runde
    with pytest.raises(InhaltFehler) as fehler:
        lies_runden_eingaben(fragen, {f"antwort_{f2}": wert})
    assert fehler.value.feld == f"antwort_{f2}"
    assert fehler.value.meldung == "Bitte einen Wert von 1 bis 5 wählen."


def test_text_grenze(runde):
    _, f1, _, fragen = runde
    with pytest.raises(InhaltFehler) as fehler:
        lies_runden_eingaben(fragen, {f"antwort_{f1}": "a" * 20_001})
    assert "höchstens 20\u00a0000 Zeichen" in fehler.value.meldung
    assert lies_runden_eingaben(fragen, {f"antwort_{f1}": "a" * 20_000})[f1][0] == "a" * 20_000


def test_fremde_felder_ignoriert(db, runde):
    _, f1, _, fragen = runde
    _, (fremd,) = testdaten.lege_runde_an(db, titel="Andere", fragen=(("freitext", "X"),))
    formular = {
        "antwort_999": "a",
        "csrf": "b",
        "anker": "c",
        f"antwort_{fremd}": "d",
        f"antwort_{f1}": "e",
    }
    assert lies_runden_eingaben(fragen, formular) == {f1: ("e", None)}


def test_speichern_neu_unveraendert_geaendert(db, lehrperson, runde):
    rid, f1, f2, _ = runde
    k = lehrperson["id"]
    eingaben = {f1: ("a", None), f2: (None, 4)}
    assert speichere_antworten(db, k, eingaben, jetzt=T1) == 2
    zeilen = antworten_der_runde(db, k, rid)
    assert all(z["erstellt"] == T1 == z["geaendert"] for z in zeilen.values())

    assert speichere_antworten(db, k, eingaben, jetzt=T2) == 0
    zeilen = antworten_der_runde(db, k, rid)
    assert all(z["erstellt"] == T1 == z["geaendert"] for z in zeilen.values())

    assert speichere_antworten(db, k, {f1: ("b", None), f2: (None, 4)}, jetzt=T3) == 1
    zeilen = antworten_der_runde(db, k, rid)
    assert (zeilen[f1]["text"], zeilen[f1]["geaendert"], zeilen[f1]["erstellt"]) == ("b", T3, T1)
    assert zeilen[f2]["geaendert"] == T1


def test_leeren_loescht(db, lehrperson, runde):
    rid, f1, f2, _ = runde
    k = lehrperson["id"]
    speichere_antworten(db, k, {f1: ("a", None), f2: (None, 4)}, jetzt=T1)
    assert speichere_antworten(db, k, {f1: (None, None), f2: (None, None)}, jetzt=T2) == 2
    assert antworten_der_runde(db, k, rid) == {}
    # Leer und nichts da: keine Aenderung.
    assert speichere_antworten(db, k, {f1: (None, None)}, jetzt=T3) == 0


def test_leeren_mit_aufnahme_behaelt_zeile(db, lehrperson, runde, einstellungen):
    rid, f1, _, _ = runde
    k = lehrperson["id"]
    aid = testdaten.lege_aufnahme_an(db, k, einstellungen.aufnahmen_verzeichnis)
    testdaten.lege_antwort_an(db, f1, k, text="Text", aufnahme_id=aid)
    assert speichere_antworten(db, k, {f1: (None, None)}, jetzt=T1) == 1
    zeile = antworten_der_runde(db, k, rid)[f1]
    assert zeile["text"] is None
    assert zeile["aufnahme_id"] == aid
    assert zeile["geaendert"] == T1


def test_transaktion_des_aufrufers(db, lehrperson, runde):
    rid, f1, _, _ = runde
    with pytest.raises(RuntimeError), transaktion(db):
        speichere_antworten(db, lehrperson["id"], {f1: ("a", None)})
        raise RuntimeError
    assert antworten_der_runde(db, lehrperson["id"], rid) == {}


def test_nur_eigenes_konto(db, lehrperson, zweite_lehrperson, runde):
    rid, f1, _, _ = runde
    testdaten.lege_antwort_an(db, f1, zweite_lehrperson["id"], text="fremd")
    speichere_antworten(db, lehrperson["id"], {f1: ("meins", None)})
    assert antworten_der_runde(db, zweite_lehrperson["id"], rid)[f1]["text"] == "fremd"
    assert antworten_der_runde(db, lehrperson["id"], rid)[f1]["text"] == "meins"
    speichere_antworten(db, lehrperson["id"], {f1: (None, None)})
    assert antworten_der_runde(db, zweite_lehrperson["id"], rid)[f1]["text"] == "fremd"


def test_rundenstand(db, lehrperson):
    a, (a1, _) = testdaten.lege_runde_an(db, titel="A")
    b, _ = testdaten.lege_runde_an(db, titel="B", fragen=())
    testdaten.lege_antwort_an(db, a1, lehrperson["id"])
    assert rundenstand(db, lehrperson["id"]) == {a: Stand(1, 2), b: Stand(0, 0)}


def test_loesche_antworten_der_runde(db, lehrperson, zweite_lehrperson, runde, einstellungen):
    rid, f1, _, _ = runde
    k = lehrperson["id"]
    verzeichnis = einstellungen.aufnahmen_verzeichnis
    aid = testdaten.lege_aufnahme_an(db, k, verzeichnis)
    datei = verzeichnis / aufnahmen_von_eintraegen(db, [aid])[0]["dateiname"]
    assert datei.exists()
    testdaten.lege_antwort_an(db, f1, k, aufnahme_id=aid)
    _, (andere,) = testdaten.lege_runde_an(db, titel="B", fragen=(("freitext", "X"),))
    testdaten.lege_antwort_an(db, andere, k)
    testdaten.lege_antwort_an(db, f1, zweite_lehrperson["id"])

    assert loesche_antworten_der_runde(db, k, rid, verzeichnis) == 1
    assert not datei.exists()
    assert aufnahmen_von_eintraegen(db, [aid]) == []
    assert antworten_der_runde(db, k, rid) == {}
    assert db.execute("SELECT COUNT(*) FROM antworten").fetchone()[0] == 2


def test_loesche_bei_fehlender_datei(db, lehrperson, runde, einstellungen):
    rid, f1, _, _ = runde
    k = lehrperson["id"]
    verzeichnis = einstellungen.aufnahmen_verzeichnis
    aid = testdaten.lege_aufnahme_an(db, k, verzeichnis)
    for datei in verzeichnis.iterdir():
        datei.unlink()
    testdaten.lege_antwort_an(db, f1, k, aufnahme_id=aid)
    assert loesche_antworten_der_runde(db, k, rid, verzeichnis) == 1
    assert db.execute("SELECT COUNT(*) FROM aufnahmen").fetchone()[0] == 0


def test_loeschen_in_laufender_transaktion(db, lehrperson, runde, einstellungen):
    rid = runde[0]
    with transaktion(db), pytest.raises(RuntimeError):
        loesche_antworten_der_runde(db, lehrperson["id"], rid, einstellungen.aufnahmen_verzeichnis)


def test_fremde_aufnahme_bleibt(db, lehrperson, zweite_lehrperson, runde, einstellungen):
    rid, f1, _, _ = runde
    verzeichnis = einstellungen.aufnahmen_verzeichnis
    fremd = testdaten.lege_aufnahme_an(db, zweite_lehrperson["id"], verzeichnis)
    name = aufnahmen_von_eintraegen(db, [fremd])[0]["dateiname"]
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], aufnahme_id=fremd)
    assert loesche_antworten_der_runde(db, lehrperson["id"], rid, verzeichnis) == 1
    assert (verzeichnis / name).exists()
    assert len(aufnahmen_von_eintraegen(db, [fremd])) == 1
