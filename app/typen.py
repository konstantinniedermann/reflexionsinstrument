"""Gemeinsame Typen fuer Routen."""

from typing import Annotated

from fastapi import Path

# Datenbank-ID: passt in einen SQLite-INTEGER. Alles andere ergibt 404.
Id = Annotated[int, Path(ge=1, le=2**63 - 1)]
