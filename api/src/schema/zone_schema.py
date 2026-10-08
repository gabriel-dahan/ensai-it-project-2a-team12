"""
Schemas for official zones (F2) and personal zonings (F4 / FO3).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ZoneTypeFilter = Literal["department", "region", "all"]


class MunicipalityResponse(BaseModel):
    insee_code: str
    name: str


class ZoneResponse(BaseModel):
    id: int | None
    name: str
    zone_type: str
    insee_code: str | None = None
    municipalities: list[MunicipalityResponse] = Field(default_factory=list)


class ZoningCreateRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    codes_insee: list[str] = Field(..., min_length=1, description="INSEE codes of the municipalities")


class ZoningUpdateRequest(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=255)
    add_codes_insee: list[str] = Field(default_factory=list)
    remove_codes_insee: list[str] = Field(default_factory=list)


class ZoningResponse(BaseModel):
    id: int | None
    name: str
    description: str | None
    created_at: date
    codes_insee: list[str]