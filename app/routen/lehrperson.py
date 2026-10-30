"""Seiten der Lehrperson."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.konten import Konto
from app.sitzung import braucht_lehrperson
from app.vorlagen import templates

router = APIRouter(prefix="/lehrperson", dependencies=[Depends(braucht_lehrperson)])


@router.get("")
def start(request: Request, konto: Annotated[Konto, Depends(braucht_lehrperson)]):
    return templates.TemplateResponse(request, "lehrperson/start.html", {"konto": konto})
