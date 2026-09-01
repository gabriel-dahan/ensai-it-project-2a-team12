"""
Schemas used by the DJU API.
"""

from datetime import date

from pydantic import BaseModel, Field


class DjuPointRequest(BaseModel):
    """
    Parameters required to calculate DJU for a geographic point.
    """

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude of the requested location",
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude of the requested location",
    )

    start_date: date = Field(
        ...,
        description="Start date of the calculation period",
    )

    end_date: date = Field(
        ...,
        description="End date of the calculation period",
    )

    heating_threshold: float = Field(
        default=18.0,
        description="Heating temperature threshold in °C",
    )

    cooling_threshold: float | None = Field(
        default=None,
        description="Cooling temperature threshold in °C",
    )

    number_of_stations: int = Field(
        default=3,
        ge=1,
        description="Number of weather stations used",
    )

    time_step: str = Field(
        default="daily",
        description="Temporal aggregation: daily, weekly, monthly or yearly",
    )