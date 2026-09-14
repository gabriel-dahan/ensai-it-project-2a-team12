"""
Business object for Météo France weather stations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from .geo_zone import _haversine_km

if TYPE_CHECKING:
    from .temperature_report import TemperatureReport


@dataclass
class MeteoStation:
    id: int | None
    station_code: str
    name: str
    latitude: float
    longitude: float
    altitude: float
   
    reports: list["TemperatureReport"] = field(default_factory=list)

    def distance_to(self, lat: float, lon: float) -> float:
        """Great-circle distance in km to a given point (haversine)."""
        return _haversine_km(self.latitude, self.longitude, lat, lon)

    def get_reports(self, start: date, end: date) -> list["TemperatureReport"]:
        return sorted(
            (r for r in self.reports if start <= r.date <= end),
            key=lambda r: r.date,
        )
    ...