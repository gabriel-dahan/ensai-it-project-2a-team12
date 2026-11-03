"""Schémas des zones officielles (F2) et des zonages personnels (F4, FO3)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ZoneTypeFilter = Literal["department", "region", "all"]


class MunicipalityResponse(BaseModel):
    insee_code: str
    name: str


class ZoneResponse(BaseModel):
    """Zone officielle sans ses communes."""

    id: int | None
    name: str
    zone_type: str
    insee_code: str | None = None


class ZoneDetailResponse(ZoneResponse):
    """Zone officielle avec ses communes."""

    municipalities: list[MunicipalityResponse]


class ZoningCreateRequest(BaseModel):
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
    description: str | None = None
    add_codes_insee: list[str] = Field(default_factory=list)
    remove_codes_insee: list[str] = Field(default_factory=list)


class ZoningResponse(BaseModel):
    id: int | None
    name: str
    description: str | None
    created_at: date
    codes_insee: list[str]
