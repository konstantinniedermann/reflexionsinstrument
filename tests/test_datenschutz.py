"""Datensparsamkeit und Löschung (#8), siehe docs/datenschutz.md und docs/loeschkonzept.md."""

import json
import re
from pathlib import Path

from app.db import migriere, verbinde

PROJEKT = Path(__file__).parent.parent
APP = PROJEKT / "app"


def _cmd_aus_dockerfile() -> list[str]:
    text = (PROJEKT / "Dockerfile").read_text(encoding="utf-8")
    zeilen = [z for z in text.splitlines() if z.startswith("CMD ")]
    assert len(zeilen) == 1
    return json.loads(zeilen[0].removeprefix("CMD "))


def test_produktion_schreibt_keine_zugriffsprotokolle():
    # Zugriffsprotokolle enthalten IP-Adressen und Pfade und landen bei fly.io.
    cmd = _cmd_aus_dockerfile()
    assert cmd[0] == "uvicorn"
    assert "--no-access-log" in cmd


def test_geloeschter_eintrag_ist_aus_der_datei_entfernt(tmp_path):
    db_pfad = tmp_path / "t.db"
    conn = verbinde(db_pfad)
    migriere(conn)
    konto = conn.execute(
        "INSERT INTO konten (anzeigename, benutzername, passwort_hash, rolle)"
        " VALUES ('A', 'a', 'x', 'lehrperson')"
    ).lastrowid
    marker = "GEHEIMER-TAGEBUCHTEXT-7f3a"
    eintrag = conn.execute(
        "INSERT INTO tagebucheintraege (konto_id, art, text) VALUES (?, 'frei', ?)",
        (konto, marker),
    ).lastrowid
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert marker.encode() in db_pfad.read_bytes()

    conn.execute("DELETE FROM tagebucheintraege WHERE id = ?", (eintrag,))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    assert marker.encode() not in db_pfad.read_bytes()


def test_vorlagen_und_css_laden_nichts_von_aussen():
    dateien = [*APP.glob("templates/**/*.html"), *APP.glob("static/**/*.css")]
    assert dateien
    # Absolute und protokoll-relative Adressen; eigene Pfade wie /static/... sind erlaubt.
    verboten = re.compile(
        r"https?://|(?:src|href)\s*=\s*['\"]?//|url\(\s*['\"]?//|@import\s+(?:url\()?['\"]?//"
    )
    for datei in dateien:
        treffer = verboten.search(datei.read_text(encoding="utf-8"))
        assert treffer is None, f"{datei.relative_to(PROJEKT)}: {treffer.group(0)!r}"
