"""Estimation des températures journalières d'un lieu à partir des stations proches."""

from datetime import date, timedelta

from business_object.meteo_station import MeteoStation
from business_object.temperature_report import TemperatureReport
from dao.meteo_station_dao import MeteoStationDao
from dao.municipality_temperature_dao import MunicipalityTemperatureDao
from dao.temperature_report_dao import TemperatureReportDao

MIN_DISTANCE_KM = 0.01  # évite une division par zéro quand le point est sur la station
CACHE_STATIONS = 3  # le cache des communes ne sert qu'avec 3 stations et l'altitude


def days_between(start_date: date, end_date: date) -> list[date]:
    """Tous les jours de start_date à end_date inclus."""
    return [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]


class TemperatureService:
    """Sélection des stations, pondération inverse à la distance et cache des communes."""

    def __init__(self, station_dao=None, report_dao=None, cache_dao=None):
        self.station_dao = station_dao or MeteoStationDao()
        self.report_dao = report_dao or TemperatureReportDao()
        self.cache_dao = cache_dao or MunicipalityTemperatureDao()

    def get_data_period(self) -> tuple[date | None, date | None]:
        """Première et dernière date des relevés disponibles."""
        return self.report_dao.get_date_range()

    def find_candidate_stations(
        self, latitude, longitude, number_of_stations, start_date, end_date
    ) -> list[MeteoStation]:
        """Les number_of_stations stations les plus proches qui ont des relevés sur la période."""
        nearest = self.station_dao.find_nearest_stations(
            latitude, longitude, limit=number_of_stations * 3
        )
        if not nearest:
            return []
        with_reports = self.report_dao.get_stations_with_reports(
            [station.id for station in nearest], start_date, end_date
        )
        candidates = [station for station in nearest if station.id in with_reports]
        return candidates[:number_of_stations]

    def estimate_daily_temperatures(
        self, latitude, longitude, altitude, stations, start_date, end_date
    ) -> list[TemperatureReport]:
        """Un relevé estimé par jour : moyenne pondérée par 1/d² des stations qui ont une valeur."""
        if not stations:
            return []
        reports_by_station = self.report_dao.get_reports_for_stations(
            [station.id for station in stations], start_date, end_date
        )

        # Pour chaque jour : sommes pondérées et sommes des poids de temp_min et temp_max
        days = {}
        for station in stations:
            distance = max(station.distance_to(latitude, longitude), MIN_DISTANCE_KM)
            weight = 1 / distance**2
            for report in reports_by_station.get(station.id, []):
                if altitude is not None and station.altitude is not None:
                    report = report.apply_altitude_correction(altitude - station.altitude)
                if report.temp_min is None and report.temp_max is None:
                    continue
                day = days.setdefault(
                    report.date,
                    {"min": 0.0, "min_w": 0.0, "max": 0.0, "max_w": 0.0, "observed": True},
                )
                if report.temp_min is not None:
                    day["min"] += weight * report.temp_min
                    day["min_w"] += weight
                if report.temp_max is not None:
                    day["max"] += weight * report.temp_max
                    day["max_w"] += weight
                if not report.observed:
                    day["observed"] = False

        estimates = []
        for day_date in sorted(days):
            day = days[day_date]
            estimates.append(
                TemperatureReport(
                    station_id=None,
                    date=day_date,
                    temp_min=day["min"] / day["min_w"] if day["min_w"] > 0 else None,
                    temp_max=day["max"] / day["max_w"] if day["max_w"] > 0 else None,
                    observed=day["observed"],
                )
            )
        return estimates

    def get_municipality_temperatures(
        self, municipality, start_date, end_date, number_of_stations=3, use_altitude=True
    ) -> list[TemperatureReport]:
        """Températures complètes (min et max) d'une commune, via le cache si possible."""
        use_cache = number_of_stations == CACHE_STATIONS and use_altitude
        all_days = days_between(start_date, end_date)

        if use_cache:
            cached = self.cache_dao.get_temperatures(municipality.id, start_date, end_date)
            cached_days = {report.date for report in cached}
            if all(day in cached_days for day in all_days):
                return [r for r in cached if r.temp_min is not None and r.temp_max is not None]

        stations = self.find_candidate_stations(
            municipality.latitude, municipality.longitude, number_of_stations, start_date, end_date
        )
        if not stations:
            return []
        altitude = municipality.altitude if use_altitude else None
        estimates = self.estimate_daily_temperatures(
            municipality.latitude, municipality.longitude, altitude, stations, start_date, end_date
        )

        if use_cache:
            # Une ligne par jour, vide si aucune estimation, pour ne plus recalculer ce jour-là
            by_date = {report.date: report for report in estimates}
            rows = [
                by_date.get(day)
                or TemperatureReport(
                    station_id=None, date=day, temp_min=None, temp_max=None, observed=False
                )
                for day in all_days
            ]
            self.cache_dao.save_temperatures(municipality.id, rows)

        return [r for r in estimates if r.temp_min is not None and r.temp_max is not None]
