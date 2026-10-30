"""Grenze fuer die Groesse einer Anfrage (reine ASGI-Middleware)."""

import re

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

GRENZE = 1024 * 1024
GRENZE_UPLOAD = 16 * 1024 * 1024  # #17: MAX_ANFRAGE_BYTES = GRENZE_UPLOAD
ZIFFERN_HOECHSTENS = 19  # Content-Length bis knapp 10^19 Bytes
UPLOAD_PFADE = (
    re.compile(r"/lehrperson/tagebuch/neu/aufnahme"),
    re.compile(r"/lehrperson/runden/\d{1,19}/fragen/\d{1,19}/aufnahme"),
)


def grenze_fuer(pfad: str) -> int:
    if any(muster.fullmatch(pfad) for muster in UPLOAD_PFADE):
        return GRENZE_UPLOAD
    return GRENZE


class ZuGross(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413)


class GroessenGrenze:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        grenze = grenze_fuer(scope["path"])
        laenge = next((w for n, w in scope["headers"] if n == b"content-length"), None)
        # Laenge der Ziffernfolge vor int() begrenzen; laengere Angaben gelten als zu gross.
        zu_gross = laenge is not None and not (
            laenge.isdigit() and len(laenge) <= ZIFFERN_HOECHSTENS and int(laenge) <= grenze
        )
        gelesen = 0

        async def begrenzt():
            nonlocal gelesen
            if zu_gross:
                raise ZuGross()
            nachricht = await receive()
            if nachricht["type"] == "http.request":
                gelesen += len(nachricht.get("body", b""))
                if gelesen > grenze:
                    raise ZuGross()
            return nachricht

        await self.app(scope, begrenzt, send)
