from pathlib import Path

import pytest

from app.eingaben import InhaltFehler
from app.texte import REGISTER, lies_text, lies_textstand, speichere_text


def test_register_vollstaendig():
    assert list(REGISTER) == [
        "begruessung",
        "hinweis_tagebuch",
        "hinweis_wer_sieht_was",
        "hinweis_gast",
        "hinweis_datenspeicherung",
        "hinweis_aufnahme",
    ]
    for key, vorlage in REGISTER.items():
        assert vorlage.schluessel == key
        assert vorlage.bezeichnung and vorlage.ort and vorlage.vorschlag
        assert (vorlage.bereich == "allgemein") == (key == "begruessung")


def test_vorschlaege_wie_datenschutz_doku():
    doku = Path("docs/datenschutz.md").read_text(encoding="utf-8")
    for key, vorlage in REGISTER.items():
        if key.startswith("hinweis_"):
            assert f"«{vorlage.vorschlag}»" in doku


def test_keine_entwicklungs_platzhalter_im_register():
    assert all("Platzhalter" not in v.vorschlag for v in REGISTER.values())


def test_ohne_zeile_gilt_vorschlag(db):
    assert lies_text(db, "hinweis_gast") == REGISTER["hinweis_gast"].vorschlag
    stand = lies_textstand(db, "hinweis_gast")
    assert stand.bestaetigt is False
    assert stand.geaendert is None


def test_speichern_bestaetigt_auch_unveraendert(db):
    speichere_text(db, "hinweis_gast", REGISTER["hinweis_gast"].vorschlag)
    stand = lies_textstand(db, "hinweis_gast")
    assert stand.bestaetigt is True
    assert stand.geaendert


def test_speichern_bereinigt(db):
    speichere_text(db, "hinweis_gast", "  a\r\nb  ")
    assert lies_text(db, "hinweis_gast") == "a\nb"


def test_leer_speichern_verboten(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_text(db, "hinweis_gast", " \n ")
    assert e.value.feld == "inhalt"
    assert str(e.value) == "Bitte einen Text eingeben."


def test_zu_lang(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_text(db, "hinweis_gast", "x" * 20_001)
    assert "höchstens 20 000 Zeichen" in str(e.value)
    speichere_text(db, "hinweis_gast", "x" * 20_000)


def test_unbekannter_schluessel(db):
    with pytest.raises(KeyError):
        speichere_text(db, "gibts_nicht", "x")
