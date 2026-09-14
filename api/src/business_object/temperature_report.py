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
    id: Optional[int]
    date: date
    temp_min: float
    temp_max: float
    temp_mean: float

    def daily_mean(self) -> float:
        """The day's mean temperature.

        Returns the station-reported `temp_mean` rather than recomputing
        (temp_min + temp_max) / 2 — Météo France provides TN/TX/TM as
        three independently measured values, not a derived average.
        """
        return self.temp_mean

    def apply_altitude_correction(self, delta_alt: float) -> "TemperatureReport":
        """Return a new report adjusted for an altitude difference.

        `delta_alt` is the target altitude minus the station's altitude,
        in meters. Positive means the target is higher (colder), negative
        means lower (warmer), applied via the standard lapse rate.
        """
        correction = -_LAPSE_RATE_C_PER_M * delta_alt
        return TemperatureReport(
            id=None,
            date=self.date,
            temp_min=self.temp_min + correction,
            temp_max=self.temp_max + correction,
            temp_mean=self.temp_mean + correction,
        )