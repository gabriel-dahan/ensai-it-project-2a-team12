"""
Schemas used by the DJU API.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

TimeStep = Literal["day", "month", "year"]


class DjuPointRequest(BaseModel):
    """
    Parameters required to calculate DJU for a geographic point.
    At least one of heating_threshold / cooling_threshold must be given
    (checked by DjuService, which answers 400 otherwise).
    """

    latitude: float = Field(..., ge=-90, le=90, description="Latitude of the requested location")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude of the requested location")
    altitude: float | None = Field(
        default=None,
        description="Altitude of the requested location in metres (optional: no altitude correction without it)",
    )
    start_date: date = Field(..., description="Start date of the calculation period")
    end_date: date = Field(..., description="End date of the calculation period")
    heating_threshold: float | None = Field(default=None, description="Heating temperature threshold in °C")
    cooling_threshold: float | None = Field(default=None, description="Cooling temperature threshold in °C")
    number_of_stations: int = Field(default=3, ge=1, description="Number of weather stations used")
    time_step: TimeStep = Field(default="day", description="Temporal aggregation: day, month or year")


class DjuZoneRequest(BaseModel):
    """
    Parameters required to calculate DJU for a zone: a department, a region,
    or one of the caller's own zonings.
    """

    zone_type: Literal["department", "region", "zoning"] = Field(..., description="Kind of zone")
    zone_id: int = Field(..., description="Id of the department / region / personal zoning")
    start_date: date = Field(..., description="Start date of the calculation period")
    end_date: date = Field(..., description="End date of the calculation period")
    heating_threshold: float | None = Field(default=None, description="Heating temperature threshold in °C")
    cooling_threshold: float | None = Field(default=None, description="Cooling temperature threshold in °C")
    number_of_stations: int = Field(default=3, ge=1, description="Number of weather stations used per municipality")
    time_step: TimeStep = Field(default="day", description="Temporal aggregation: day, month or year")


class DjuResultItem(BaseModel):
    period_start: date
    period_end: date
    value: float


class DjuResponse(BaseModel):
    """One entry per requested threshold: 'heating' and/or 'cooling'."""

    calculation_ids: dict[str, int | None]
    results: dict[str, list[DjuResultItem]]