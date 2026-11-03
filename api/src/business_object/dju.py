"""Calcul des DJU (degrés-jours unifiés)."""

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta

from .geo_zone import GeographicZone
from .meteo_station import MeteoStation
from .temperature_report import TemperatureReport

TIME_STEPS = ("day", "week", "month", "year")  # week = semaine ISO, du lundi au dimanche


def period_bounds(day: date, time_step: str) -> tuple[date, date]:
    """Début et fin (calendaires) de la période qui contient le jour."""
    if time_step == "day":
        return day, day
    if time_step == "week":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    if time_step == "month":
        last_day = monthrange(day.year, day.month)[1]
        return date(day.year, day.month, 1), date(day.year, day.month, last_day)
    if time_step == "year":
        return date(day.year, 1, 1), date(day.year, 12, 31)
    raise ValueError(f"Pas de temps inconnu : {time_step!r} (attendu : {', '.join(TIME_STEPS)})")


@dataclass
class DjuType:
    id: int | None
    name: str
    base_temperature: float
    mode: str  # "heating" ou "cooling"

    def compute_daily_value(self, t_min: float, t_max: float) -> float:
        """DJU d'un jour à partir de la moyenne (t_min + t_max) / 2."""
        mean = (t_min + t_max) / 2
        if self.is_heating():
            return max(0.0, self.base_temperature - mean)
        return max(0.0, mean - self.base_temperature)

    def is_heating(self) -> bool:
        return self.mode == "heating"

    def is_cooling(self) -> bool:
        return self.mode == "cooling"


@dataclass
class DjuResult:
    id: int | None
    period_start: date
    period_end: date
    value: float
    days_with_data: int  # jours de la période réellement calculés
    observed_ratio: float  # part de ces jours calculés uniquement avec des mesures observées


@dataclass
class DjuCalculation:
    id: int | None
    start_date: date
    end_date: date
    time_step: str
    type: DjuType
    zone: GeographicZone | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    number_of_stations: int = 3
    use_altitude: bool = True
    computed_at: date | None = None
    results: list[DjuResult] = field(default_factory=list)
    candidate_stations: list[MeteoStation] = field(default_factory=list)
    # DJU de chaque jour : date -> (valeur, observé)
    daily_values: dict[date, tuple[float, bool]] = field(default_factory=dict, init=False, repr=False, compare=False)

    def _is_usable(self, report: TemperatureReport) -> bool:
        """Vrai si le relevé est dans la période et a ses deux températures."""
        return (
            self.start_date <= report.date <= self.end_date
            and report.temp_min is not None
            and report.temp_max is not None
        )

    def run(self, daily_temperatures: list[TemperatureReport]) -> list[DjuResult]:
        """Calcule les DJU d'un point à partir de ses températures journalières."""
        self.daily_values = {}
        for report in daily_temperatures:
            if self._is_usable(report):
                value = self.type.compute_daily_value(report.temp_min, report.temp_max)
                self.daily_values[report.date] = (value, report.observed)
        self.results = self.aggregate(self.time_step)
        self.computed_at = date.today()
        return self.results

    def run_for_zone(
        self, temperatures_by_municipality: dict[str, list[TemperatureReport]]
    ) -> list[DjuResult]:
        """Calcule les DJU d'une zone : moyenne des communes pondérée par la population."""
        if self.zone is None:
            raise ValueError("run_for_zone demande une zone")
        municipalities = self.zone.get_municipalities()

        # Poids = population (0 si inconnue) ; si tous les poids sont nuls, poids 1 pour tous
        weights = {m.insee_code: m.population if m.population and m.population > 0 else 0
                   for m in municipalities}
        if all(w == 0 for w in weights.values()):
            weights = {code: 1 for code in weights}

        weighted_sum: dict[date, float] = {}
        weight_total: dict[date, float] = {}
        observed: dict[date, bool] = {}
        for code, weight in weights.items():
            if weight == 0:
                continue
            for report in temperatures_by_municipality.get(code, []):
                if not self._is_usable(report):
                    continue
                day = report.date
                value = self.type.compute_daily_value(report.temp_min, report.temp_max)
                weighted_sum[day] = weighted_sum.get(day, 0.0) + weight * value
                weight_total[day] = weight_total.get(day, 0) + weight
                observed[day] = observed.get(day, True) and report.observed

        self.daily_values = {
            day: (weighted_sum[day] / weight_total[day], observed[day]) for day in weighted_sum
        }
        self.results = self.aggregate(self.time_step)
        self.computed_at = date.today()
        return self.results

    def aggregate(self, time_step: str) -> list[DjuResult]:
        """Cumule les DJU journaliers par jour, semaine, mois ou année."""
        if time_step not in TIME_STEPS:
            raise ValueError(f"Pas de temps inconnu : {time_step!r} (attendu : {', '.join(TIME_STEPS)})")

        # Clé = (début, fin) de la période, ramenés à [start_date, end_date]
        groups: dict[tuple[date, date], list[tuple[float, bool]]] = {}
        for day, day_value in self.daily_values.items():
            start, end = period_bounds(day, time_step)
            key = (max(start, self.start_date), min(end, self.end_date))
            groups.setdefault(key, []).append(day_value)

        results = []
        for (start, end), values in groups.items():
            nb_observed = sum(1 for _, is_observed in values if is_observed)
            results.append(
                DjuResult(
                    id=None,
                    period_start=start,
                    period_end=end,
                    value=sum(value for value, _ in values),
                    days_with_data=len(values),
                    observed_ratio=nb_observed / len(values),
                )
            )
        results.sort(key=lambda r: r.period_start)
        return results
