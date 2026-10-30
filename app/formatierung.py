"""Einfache Formatierung langer Texte, sicher gegen eingeschleustes HTML."""

import re

from markupsafe import Markup, escape

_LISTENZEILE = re.compile(r"^\s*[-*•][ \t]+(\S.*)$")
_FETT = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
_LEERZEILE = re.compile(r"\n\s*\n")


def _zeile(text: str) -> str:
    """Escapt zuerst, setzt erst danach die festen Tags ein."""
    return _FETT.sub(r"<strong>\1</strong>", str(escape(text)))


def _block(zeilen: list[str]) -> str:
    laeufe: list[tuple[bool, list[str]]] = []
    for zeile in zeilen:
        treffer = _LISTENZEILE.match(zeile)
        ist_liste = treffer is not None
        inhalt = treffer.group(1) if treffer else zeile
        if laeufe and laeufe[-1][0] == ist_liste:
            laeufe[-1][1].append(inhalt)
        else:
            laeufe.append((ist_liste, [inhalt]))
    teile = []
    for ist_liste, inhalte in laeufe:
        if ist_liste:
            teile.append("<ul>" + "".join(f"<li>{_zeile(i)}</li>" for i in inhalte) + "</ul>")
        else:
            teile.append("<p>" + "<br>".join(_zeile(i) for i in inhalte) + "</p>")
    return "".join(teile)


def formatiere(text: str | None) -> Markup:
    if not text:
        return Markup("")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(zeile.rstrip() for zeile in text.split("\n")).strip("\n")
    if not text.strip():
        return Markup("")
    bloecke = _LEERZEILE.split(text)
    return Markup("".join(_block(b.split("\n")) for b in bloecke if b.strip()))
