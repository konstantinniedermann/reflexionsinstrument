"""Cookies: Set-Cookie-Werte vormerken und per ASGI-Middleware an die Antwort haengen."""

import secrets
from http.cookies import SimpleCookie

from starlette.requests import Request

CSRF_MAX_AGE = 30 * 24 * 3600


def _baue_cookie(request: Request, name: str, wert: str, max_age: int | None) -> str:
    cookie: SimpleCookie = SimpleCookie()
    cookie[name] = wert
    morsel = cookie[name]
    morsel["path"] = "/"
    morsel["httponly"] = True
    morsel["samesite"] = "Lax"
    if request.app.state.einstellungen.produktion:
        morsel["secure"] = True
    if max_age is not None:
        morsel["max-age"] = max_age
    return morsel.OutputString()


def _merke(request: Request, name: str, wert: str, max_age: int | None) -> None:
    ausstehend: list[str] = request.state.cookies_ausstehend
    # Ein spaeterer Aufruf fuer denselben Namen ersetzt den frueheren.
    ausstehend[:] = [c for c in ausstehend if not c.startswith(f"{name}=")]
    ausstehend.append(_baue_cookie(request, name, wert, max_age))


def setze_cookie(request: Request, name: str, wert: str, max_age: int | None) -> None:
    _merke(request, name, wert, max_age)


def loesche_cookie(request: Request, name: str) -> None:
    _merke(request, name, "", 0)


class CookieMiddleware:
    """Stellt `csrf_wert` bereit und haengt vorgemerkte Cookies an jede Antwort."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        zustand = scope.setdefault("state", {})
        zustand["cookies_ausstehend"] = []
        anfrage = Request(scope)
        vorhanden = anfrage.cookies.get("csrf")
        if vorhanden:
            zustand["csrf_wert"] = vorhanden
        else:
            zustand["csrf_wert"] = secrets.token_urlsafe(32)
            setze_cookie(anfrage, "csrf", zustand["csrf_wert"], CSRF_MAX_AGE)
        ausstehend: list[str] = zustand["cookies_ausstehend"]

        async def send_mit_cookies(nachricht):
            if nachricht["type"] == "http.response.start":
                zusaetzlich = [(b"set-cookie", c.encode("latin-1")) for c in ausstehend]
                nachricht = {
                    **nachricht,
                    "headers": list(nachricht.get("headers", [])) + zusaetzlich,
                }
            await send(nachricht)

        await self.app(scope, receive, send_mit_cookies)
