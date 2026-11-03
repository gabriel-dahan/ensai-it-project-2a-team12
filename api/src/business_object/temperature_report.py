"""
Business object for a single day's temperature reading at a station.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

_LAPSE_RATE_C_PER_M = 0.0065


@dataclass
class TemperatureReport:
    """One day of temperatures, measured at a station or estimated for a place.

    `station_id` is None for an estimated report. In the database, temp_min or
    temp_max can be missing (NULL): such reports must be skipped before any calculation.
    """

    id: Optional[int]
    station_id: Optional[int]
    date: date
    temp_min: Optional[float]
    temp_max: Optional[float]

    def daily_mean(self) -> float:
        """The day's mean temperature, (temp_min + temp_max) / 2 as in the DJU reference method."""
        return (self.temp_min + self.temp_max) / 2

    def apply_altitude_correction(self, delta_alt: float) -> "TemperatureReport":
        """Return a new report adjusted for an altitude difference.

        `delta_alt` is the target altitude minus the station's altitude,
        in meters. Positive means the target is higher (colder), negative
        means lower (warmer), applied via the standard lapse rate.
        """
        correction = -_LAPSE_RATE_C_PER_M * delta_alt
        return TemperatureReport(
            id=None,
            station_id=self.station_id,
            date=self.date,
            temp_min=self.temp_min + correction,
            temp_max=self.temp_max + correction,
        )