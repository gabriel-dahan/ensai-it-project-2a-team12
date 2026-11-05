"""Calcul des DJU (degrés-jours unifiés)."""

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .geo_zone import GeographicZone
from .meteo_station import MeteoStation

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

    def compute_daily_value(self, t_mean):
        """DJU d'un jour à partir de la température moyenne (Tmin + Tmax) / 2.

        t_mean peut être un nombre ou un tableau pandas (une valeur par jour, voire par commune).
        """
        if self.is_heating():
            return np.maximum(0.0, self.base_temperature - t_mean)
        return np.maximum(0.0, t_mean - self.base_temperature)

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

    def run(self, daily_means: pd.Series, daily_observed: pd.Series) -> list[DjuResult]:
        """Calcule les DJU d'un point à partir de ses températures moyennes journalières.

        daily_means : température moyenne indexée par date (NaN si inconnue) ;
        daily_observed : vrai si la valeur du jour ne repose que sur des mesures observées.
        """
        self._set_daily_values(self.type.compute_daily_value(daily_means), daily_observed)
        self.results = self.aggregate(self.time_step)
        self.computed_at = date.today()
        return self.results

    def run_for_zone(self, means: pd.DataFrame, observed: pd.DataFrame) -> list[DjuResult]:
        """Calcule les DJU d'une zone : moyenne des communes pondérée par la population.

        means et observed ont une ligne par date et une colonne par code INSEE ;
        seules les colonnes des communes de la zone sont utilisées.
        """
        if self.zone is None:
            raise ValueError("run_for_zone demande une zone")
        municipalities = self.zone.get_municipalities()

        # Poids = population (0 si inconnue) ; si tous les poids sont nuls, poids 1 pour tous
        weights = {m.insee_code: m.population if m.population and m.population > 0 else 0
                   for m in municipalities}
        if all(w == 0 for w in weights.values()):
            weights = {code: 1 for code in weights}
        weights = pd.Series({code: w for code, w in weights.items() if w > 0 and code in means.columns},
                            dtype=float)
        codes = list(weights.index)

        # DJU de chaque commune chaque jour, puis moyenne pondérée sur les communes qui ont une valeur
        dju = self.type.compute_daily_value(means[codes])
        has_value = dju.notna()
        weighted_sum = dju.mul(weights, axis=1).sum(axis=1)
        weight_total = has_value.mul(weights, axis=1).sum(axis=1)
        daily_dju = weighted_sum / weight_total.where(weight_total > 0)
        daily_observed = (observed[codes] | ~has_value).all(axis=1)

        self._set_daily_values(daily_dju, daily_observed)
        self.results = self.aggregate(self.time_step)
        self.computed_at = date.today()
        return self.results

    def _set_daily_values(self, daily_dju: pd.Series, daily_observed: pd.Series) -> None:
        """Garde les DJU journaliers connus et compris dans la période demandée."""
        known = daily_dju.notna().to_numpy()
        self.daily_values = {
            day: (float(value), bool(is_observed))
            for day, value, is_observed in zip(
                daily_dju.index[known], daily_dju.to_numpy()[known], daily_observed.to_numpy()[known]
            )
            if self.start_date <= day <= self.end_date
        }

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
