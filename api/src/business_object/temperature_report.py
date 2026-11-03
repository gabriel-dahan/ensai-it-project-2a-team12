"""Températures minimale et maximale d'un jour."""

from dataclasses import dataclass
from datetime import date

LAPSE_RATE = 0.0065  # °C par mètre


@dataclass
class TemperatureReport:
    station_id: int | None
    date: date
    temp_min: float | None
    temp_max: float | None
    observed: bool = True  # False si la valeur est comblée ou estimée à partir de valeurs comblées
    id: int | None = None

    def daily_mean(self) -> float | None:
        """Moyenne (min + max) / 2, None si une valeur manque."""
        if self.temp_min is None or self.temp_max is None:
            return None
        return (self.temp_min + self.temp_max) / 2

    def apply_altitude_correction(self, delta_alt: float) -> "TemperatureReport":
        """Nouveau relevé corrigé ; delta_alt = altitude cible - altitude station (m)."""
        correction = -LAPSE_RATE * delta_alt
        new_min = None if self.temp_min is None else self.temp_min + correction
        new_max = None if self.temp_max is None else self.temp_max + correction
        return TemperatureReport(
            station_id=self.station_id,
            date=self.date,
            temp_min=new_min,
            temp_max=new_max,
            observed=self.observed,
        )
