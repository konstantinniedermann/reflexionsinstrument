"""Versand der Benachrichtigungen: Verschlüsselung, Signatur, Umgang mit Antworten (#37)."""

import base64
import http.client
import json
import logging
import os
import urllib.error
import urllib.request

import http_ece
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.push import (
    Ergebnis,
    erzeuge_vapid_schluessel,
    lade_vapid,
    oeffentlicher_schluessel,
    verschicke_an_alle,
)
from app.push_abos import Abo, alle_abos, anzahl_abos, speichere_abo

ENDPUNKT = "https://fcm.googleapis.com/fcm/send/geheimer-pfad-123"


def _b64(daten: bytes) -> str:
    return base64.urlsafe_b64encode(daten).rstrip(b"=").decode()


def _unb64(wert: str) -> bytes:
    return base64.urlsafe_b64decode(wert + "=" * (-len(wert) % 4))


class Geraet:
    def __init__(self, endpunkt=ENDPUNKT):
        self.schluessel = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        punkt = self.schluessel.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.abo = Abo(endpunkt, _b64(punkt), _b64(self.auth))

    def entschluessele(self, koerper: bytes) -> dict:
        klar = http_ece.decrypt(
            koerper, private_key=self.schluessel, auth_secret=self.auth, version="aes128gcm"
        )
        return json.loads(klar)


class Dienst:
    """Ersatz für urlopen: hält jede Anfrage fest und antwortet mit vorgegebenen Status."""

    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.anfragen = []

    def __call__(self, anfrage, timeout):
        self.anfragen.append(anfrage)
        self.timeout = timeout
        antwort = self.antworten.pop(0)
        if isinstance(antwort, Exception):
            raise antwort
        if antwort >= 400:
            raise urllib.error.HTTPError(anfrage.full_url, antwort, "x", {}, None)

        class Antwort:
            status = antwort

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Antwort()


@pytest.fixture
def vapid():
    return lade_vapid(erzeuge_vapid_schluessel())


def test_nutzlast_entschluesselbar(db, lehrperson, vapid):
    geraet = Geraet()
    speichere_abo(db, lehrperson["id"], geraet.abo)
    dienst = Dienst(201)
    ergebnis = verschicke_an_alle(db, vapid, "Reflexion", "Neuer Impuls", oeffne=dienst)
    assert ergebnis == Ergebnis(gesendet=1, entfernt=0, nicht_erreicht=0)
    assert geraet.entschluessele(dienst.anfragen[0].data) == {
        "titel": "Reflexion",
        "text": "Neuer Impuls",
    }


def test_header(db, lehrperson, vapid):
    speichere_abo(db, lehrperson["id"], Geraet().abo)
    dienst = Dienst(201)
    verschicke_an_alle(db, vapid, "T", "x", oeffne=dienst)
    anfrage = dienst.anfragen[0]
    assert anfrage.full_url == ENDPUNKT
    assert anfrage.get_method() == "POST"
    assert anfrage.get_header("Ttl") == "86400"
    assert anfrage.get_header("Urgency") == "normal"
    assert anfrage.get_header("Content-encoding") == "aes128gcm"
    assert dienst.timeout == 10
    autorisierung = anfrage.get_header("Authorization")
    assert autorisierung.startswith("vapid t=")
    teile = dict(t.split("=", 1) for t in autorisierung[len("vapid ") :].split(","))
    assert teile["k"] == oeffentlicher_schluessel(vapid)
    anspruch = json.loads(_unb64(teile["t"].split(".")[1]))
    assert anspruch["aud"] == "https://fcm.googleapis.com"
    assert anspruch["sub"] == "https://reflexionsinstrument.fly.dev"


@pytest.mark.parametrize("status", [404, 410])
def test_ungueltiges_abo_wird_entfernt(db, lehrperson, vapid, status):
    speichere_abo(db, lehrperson["id"], Geraet().abo)
    ergebnis = verschicke_an_alle(db, vapid, "T", "x", oeffne=Dienst(status))
    assert ergebnis == Ergebnis(gesendet=0, entfernt=1, nicht_erreicht=0)
    assert anzahl_abos(db) == 0


@pytest.mark.parametrize("status", [500, 401, 403, 301])
def test_andere_antworten_abo_bleibt(db, lehrperson, vapid, status):
    # 401/403 kann auch ein Fehler auf unserer Seite sein (Signatur); dann nicht alle Abos löschen.
    speichere_abo(db, lehrperson["id"], Geraet().abo)
    ergebnis = verschicke_an_alle(db, vapid, "T", "x", oeffne=Dienst(status))
    assert ergebnis == Ergebnis(gesendet=0, entfernt=0, nicht_erreicht=1)
    assert anzahl_abos(db) == 1


def test_netzfehler_andere_bekommen_es(db, lehrperson, zweite_lehrperson, vapid):
    speichere_abo(db, lehrperson["id"], Geraet(ENDPUNKT + "a").abo)
    speichere_abo(db, zweite_lehrperson["id"], Geraet(ENDPUNKT + "b").abo)
    dienst = Dienst(urllib.error.URLError("weg"), 201)
    ergebnis = verschicke_an_alle(db, vapid, "T", "x", oeffne=dienst)
    assert ergebnis == Ergebnis(gesendet=1, entfernt=0, nicht_erreicht=1)
    assert len(alle_abos(db)) == 2


def test_zeitueberschreitung_zaehlt_als_nicht_erreicht(db, lehrperson, vapid):
    speichere_abo(db, lehrperson["id"], Geraet().abo)
    ergebnis = verschicke_an_alle(db, vapid, "T", "x", oeffne=Dienst(TimeoutError()))
    assert ergebnis.nicht_erreicht == 1


def test_log_ohne_endpunkt_und_text(db, lehrperson, vapid, caplog):
    speichere_abo(db, lehrperson["id"], Geraet().abo)
    with caplog.at_level(logging.INFO):
        verschicke_an_alle(db, vapid, "T", "Geheimer Text", oeffne=Dienst(500))
    assert "fcm.googleapis.com" in caplog.text
    assert "geheimer-pfad" not in caplog.text
    assert "Geheimer Text" not in caplog.text


@pytest.mark.parametrize(
    "fehler",
    [
        http.client.InvalidURL("x"),
        http.client.BadStatusLine("x"),
        UnicodeEncodeError("ascii", "ä", 0, 1, "x"),
    ],
)
def test_unerwarteter_fehler_andere_bekommen_es(db, lehrperson, zweite_lehrperson, vapid, fehler):
    speichere_abo(db, lehrperson["id"], Geraet(ENDPUNKT + "a").abo)
    speichere_abo(db, zweite_lehrperson["id"], Geraet(ENDPUNKT + "b").abo)
    ergebnis = verschicke_an_alle(db, vapid, "T", "x", oeffne=Dienst(fehler, 201))
    assert ergebnis == Ergebnis(gesendet=1, entfernt=0, nicht_erreicht=1)


def test_folgt_keiner_weiterleitung(db, lehrperson, vapid, monkeypatch):
    """Der echte Versand folgt keiner Weiterleitung (die Signatur ginge sonst an ein anderes Ziel)."""
    from app import push

    angefragt = []

    class Weiterleitung(http.client.HTTPResponse):
        pass

    def antwort_302(self, anfrage):
        angefragt.append(anfrage.full_url)
        kopf = http.client.HTTPMessage()
        kopf["Location"] = "https://127.0.0.1/innen"
        return push._OHNE_WEITERLEITUNG.error("https", anfrage, None, 302, "Found", kopf)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", antwort_302)
    speichere_abo(db, lehrperson["id"], Geraet().abo)
    ergebnis = verschicke_an_alle(db, vapid, "T", "x")
    assert angefragt == [ENDPUNKT]
    assert ergebnis.nicht_erreicht == 1
