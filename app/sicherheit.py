"""Sicherheits-Header fuer jede HTTP-Antwort (reine ASGI-Middleware)."""

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def sicherheits_header(produktion: bool) -> dict[str, str]:
    header = {
        "Content-Security-Policy": CSP,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
        "X-Frame-Options": "DENY",
    }
    if produktion:
        header["Strict-Transport-Security"] = "max-age=31536000"
    return header


class SicherheitsHeaderMiddleware:
    def __init__(self, app, produktion: bool):
        self.app = app
        self._header = [
            (name.lower().encode("latin-1"), wert.encode("latin-1"))
            for name, wert in sicherheits_header(produktion).items()
        ]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_mit_headern(nachricht):
            if nachricht["type"] == "http.response.start":
                gesetzt = {name for name, _ in self._header}
                vorhanden = [h for h in nachricht.get("headers", []) if h[0].lower() not in gesetzt]
                nachricht = {**nachricht, "headers": vorhanden + self._header}
            await send(nachricht)

        await self.app(scope, receive, send_mit_headern)
