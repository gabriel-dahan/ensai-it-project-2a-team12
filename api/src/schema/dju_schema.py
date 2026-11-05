"""Schémas des calculs de DJU (F1, F3)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

TimeStep = Literal["day", "week", "month", "year"]
AggregationLevel = Literal["zone", "department", "municipality"]
OutputFormat = Literal["json", "csv"]


class DjuPointRequest(BaseModel):
    """Paramètres d'un calcul de DJU en un point (F1)."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude: float | None = Field(default=None, description="Altitude en mètres (facultative)")
    start_date: date
    end_date: date
    heating_threshold: float | None = Field(default=None, description="Seuil de chauffage en °C")
    cooling_threshold: float | None = Field(default=None, description="Seuil de climatisation en °C")
    number_of_stations: int = Field(default=3, ge=1, le=10)
    time_step: TimeStep = "day"


class DjuZoneRequest(BaseModel):
    """Paramètres d'un calcul de DJU sur un territoire (F3)."""

    zone_type: Literal["department", "region", "zoning"]
    zone_id: int
    aggregation_level: AggregationLevel = "zone"
    start_date: date
    end_date: date
    heating_threshold: float | None = Field(default=None, description="Seuil de chauffage en °C")
    cooling_threshold: float | None = Field(default=None, description="Seuil de climatisation en °C")
    number_of_stations: int = Field(default=3, ge=1, le=10)
    use_altitude: bool = True
    time_step: TimeStep = "day"


class DjuResultItem(BaseModel):
    """Valeur de DJU sur une période."""

    period_start: date
    period_end: date
    value: float
    days_with_data: int
    observed_ratio: float


class DjuResponse(BaseModel):
    """Résultats d'un point, par mode ("heating" et/ou "cooling")."""

    results: dict[str, list[DjuResultItem]]
    warning: str | None = Field(default=None, description="Présent si la période a été raccourcie")


class DjuZoneResult(BaseModel):
    """Résultats d'une sous-zone, par mode."""

    zone_type: str
    zone_id: int | None
    name: str
    results: dict[str, list[DjuResultItem]]


class DjuZoneResponse(BaseModel):
    """Résultats d'un territoire, une entrée par sous-zone."""

    zones: list[DjuZoneResult]
    warning: str | None = Field(default=None, description="Présent si la période a été raccourcie")
