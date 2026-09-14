""" computing DJU (Degrés Jours Unifiés).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .geo_zone import GeographicZone
    from .meteo_station import MeteoStation
    from .user import User


_VALID_TIME_STEPS = ("day", "month", "year")


def _period_key(d: date, time_step: str) -> tuple:
    if time_step == "day":
        return (d.year, d.month, d.day)
    if time_step == "month":
        return (d.year, d.month)
    if time_step == "year":
        return (d.year,)
    raise ValueError(f"Unsupported time_step: {time_step!r}, expected one of {_VALID_TIME_STEPS}")


@dataclass
class DjuType:
    id: Optional[int]
    name: str
    base_temperature: float
    mode: str  # "heating" or "cooling"

    def compute_daily_value(self, t_min: float, t_max: float) -> float:
        """DJU for a single day from that day's min/max temperature.

        Uses the unified degree-day method: daily mean = (t_min + t_max) / 2,
        then the departure from the base temperature, clamped at zero.
        """
        daily_mean = (t_min + t_max) / 2
        if self.is_heating():
            return max(0.0, self.base_temperature - daily_mean)
        return max(0.0, daily_mean - self.base_temperature)

    def is_heating(self) -> bool:
        return self.mode == "heating"

    def is_cooling(self) -> bool:
        return self.mode == "cooling"


@dataclass
class DjuResult:
    id: Optional[int]
    period_start: date
    period_end: date
    value: float

    def merge(self, other: "DjuResult") -> "DjuResult":
        """Combine two results into one covering their union period.

        DJU values are additive over time, so the merged value is the sum.
        Returns a new DjuResult rather than mutating either operand.
        """
        return DjuResult(
            id=None,
            period_start=min(self.period_start, other.period_start),
            period_end=max(self.period_end, other.period_end),
            value=self.value + other.value,
        )


@dataclass
class DjuCalculation:
    id: Optional[int]
    start_date: date
    end_date: date
    time_step: str
    type: DjuType
    # Exactly one of `zone` or (`latitude`, `longitude`) should be set.
    zone: Optional["GeographicZone"] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Implied by User "1" --> "*" DjuCalculation, as with Zoning.owner.
    owner: Optional["User"] = None
    computed_at: Optional[date] = None
    results: list[DjuResult] = field(default_factory=list)
    # Candidate stations for a point-based calculation (no zone to derive
    # them from).
    candidate_stations: list["MeteoStation"] = field(default_factory=list)
    # Raw per-day DJU values, kept so aggregate() can be re-run with a
    # different time_step without recomputing from temperature reports.
    _daily_values: dict[date, float] = field(default_factory=dict, repr=False)

    def run(self) -> list[DjuResult]:
        if self.time_step not in _VALID_TIME_STEPS:
            raise ValueError(f"Unsupported time_step: {self.time_step!r}")

        self._daily_values = self._compute_daily_values()
        self.results = self.aggregate(self.time_step)
        self.computed_at = date.today()
        return self.results

    def aggregate(self, time_step: str) -> list[DjuResult]:
        """Group the raw daily DJU values into periods of `time_step`.

        Can be called again with a different granularity than the one used
        in run(), as long as run() has already populated the daily values.
        """
        if not self._daily_values:
            raise RuntimeError("aggregate() called before any daily values were computed — call run() first")

        groups: dict[tuple, list[date]] = defaultdict(list)
        for day in self._daily_values:
            groups[_period_key(day, time_step)].append(day)

        results = []
        for days in groups.values():
            days.sort()
            total = sum(self._daily_values[d] for d in days)
            results.append(DjuResult(id=None, period_start=days[0], period_end=days[-1], value=total))
        results.sort(key=lambda r: r.period_start)
        return results

    def can_reuse_intermediate(self) -> bool:
        """True if daily values are already computed and can be re-aggregated
        with a different time_step instead of recomputing from scratch."""
        return bool(self._daily_values)

    def _compute_daily_values(self) -> dict[date, float]:
        if self.zone is not None:
            return self._compute_daily_values_for_zone()
        if self.latitude is not None and self.longitude is not None:
            return self._compute_daily_values_for_point()
        raise ValueError("DjuCalculation needs either a zone or a (latitude, longitude) point")

    def _compute_daily_values_for_zone(self) -> dict[date, float]:
        per_day: dict[date, list[float]] = defaultdict(list)
        for municipality in self.zone.get_municipalities():
            nearest = municipality.get_nearby_stations(1)
            if not nearest:
                continue
            for report in nearest[0].get_reports(self.start_date, self.end_date):
                per_day[report.date].append(self.type.compute_daily_value(report.temp_min, report.temp_max))
        # Zone-level daily value = average across the zone's municipalities.
        return {day: sum(values) / len(values) for day, values in per_day.items()}

    def _compute_daily_values_for_point(self) -> dict[date, float]:
        if not self.candidate_stations:
            return {}
        nearest = min(
            self.candidate_stations,
            key=lambda s: s.distance_to(self.latitude, self.longitude),
        )
        return {
            report.date: self.type.compute_daily_value(report.temp_min, report.temp_max)
            for report in nearest.get_reports(self.start_date, self.end_date)
        }