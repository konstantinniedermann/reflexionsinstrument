"""Jinja2-Templates, eigenes Modul, damit Router-Module sie ohne Zirkelimport nutzen."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
