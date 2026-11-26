"""Schémas des zones officielles (F2) et des zonages personnels (F4, FO3)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ZoneTypeFilter = Literal["department", "region", "all"]


class MunicipalityResponse(BaseModel):
    """Commune d'une zone : code INSEE et nom."""

    insee_code: str
    name: str


class ZoneResponse(BaseModel):
    """Zone officielle sans ses communes ; insee_code sert à la désigner dans les autres routes."""

    insee_code: str
    name: str
    zone_type: str


class ZoneDetailResponse(ZoneResponse):
    """Zone officielle avec ses communes."""

    municipalities: list[MunicipalityResponse]


class ZoningCreateRequest(BaseModel):
    """Création d'un zonage : nom, description et codes INSEE des communes."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    codes_insee: list[str] = Field(..., min_length=1)


class ZoningImportRequest(BaseModel):
    """Contenu d'un fichier CSV ou JSON envoyé sous forme de texte."""

    filename: str
    content: str
    name: str | None = None
    description: str | None = None


class ZoningUpdateRequest(BaseModel):
    """Modification d'un zonage : description, communes à ajouter ou à retirer."""

    description: str | None = None
    add_codes_insee: list[str] = Field(default_factory=list)
    remove_codes_insee: list[str] = Field(default_factory=list)


class ZoningResponse(BaseModel):
    """Zonage renvoyé par l'API, avec les codes INSEE de ses communes."""

    id: int | None
    name: str
    description: str | None
    created_at: date
    codes_insee: list[str]
