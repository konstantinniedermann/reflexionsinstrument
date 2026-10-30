"""CSRF-Schutz: Cookie-Wert plus HMAC-Token im Formular."""

import hashlib
import hmac
import secrets

from markupsafe import Markup, escape
from starlette.requests import Request

from app.cookies import CSRF_MAX_AGE, setze_cookie
from app.zugriff import KeinZugriff


def csrf_token(request: Request) -> str:
    schluessel = request.app.state.einstellungen.geheimer_schluessel.encode("utf-8")
    nachricht = ("csrf:" + request.state.csrf_wert).encode("utf-8")
    return hmac.new(schluessel, nachricht, hashlib.sha256).hexdigest()


def csrf_feld(request: Request) -> Markup:
    return Markup('<input type="hidden" name="csrf" value="{}">').format(
        escape(csrf_token(request))
    )


def erneuere_csrf(request: Request) -> None:
    request.state.csrf_wert = secrets.token_urlsafe(32)
    setze_cookie(request, "csrf", request.state.csrf_wert, CSRF_MAX_AGE)


async def pruefe_csrf(request: Request) -> None:
    formular = await request.form()
    eingereicht = formular.get("csrf")
    if not isinstance(eingereicht, str) or not hmac.compare_digest(
        eingereicht.encode("utf-8"), csrf_token(request).encode("utf-8")
    ):
        raise KeinZugriff(
            "Das Formular ist abgelaufen. Bitte die Seite neu laden.", titel="Formular abgelaufen"
        )
