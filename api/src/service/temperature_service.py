"""Estimation des températures journalières de lieux à partir des stations proches."""

from datetime import date

import numpy as np
import pandas as pd

from business_object.geo_zone import EARTH_RADIUS_KM, Municipality
from business_object.meteo_station import MeteoStation
from business_object.temperature_report import LAPSE_RATE
from dao.meteo_station_dao import MeteoStationDao
from dao.temperature_report_dao import REPORT_COLUMNS, TemperatureReportDao

MIN_DISTANCE_KM = 0.01  # évite une division par zéro quand le lieu est sur la station
MAX_CANDIDATES = 50  # stations les plus proches examinées pour chaque lieu

# Un lieu : clé -> (latitude, longitude, altitude ou None si pas de correction d'altitude)
Locations = dict[str, tuple[float, float, float | None]]


def distances_km(lat: float, lon: float, latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
    """Distances (formule de Haversine) en km entre un point et un tableau de positions."""
    lat1, lon1 = np.radians(lat), np.radians(lon)
    lat2, lon2 = np.radians(latitudes), np.radians(longitudes)
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


class TemperatureService:
    """Sélection des stations et pondération inverse à la distance, pour plusieurs lieux à la fois."""

    def __init__(self, station_dao=None, report_dao=None):
        self.station_dao = station_dao or MeteoStationDao()
        self.report_dao = report_dao or TemperatureReportDao()

    def get_data_period(self) -> tuple[date | None, date | None]:
        """Première et dernière date des relevés disponibles."""
        return self.report_dao.get_date_range()

    def find_candidate_stations(
        self, locations: Locations, number_of_stations: int, start_date: date, end_date: date
    ) -> tuple[dict[str, list[MeteoStation]], pd.DataFrame]:
        """Pour chaque lieu, ses number_of_stations stations les plus proches qui ont des relevés.

        Renvoie aussi les relevés de toutes ces stations, lus une seule fois même si une
        station sert à plusieurs lieux.
        """
        stations = self.station_dao.get_all_stations()
        latitudes = np.array([s.latitude for s in stations])
        longitudes = np.array([s.longitude for s in stations])

        # Pour chaque lieu : indices des stations, de la plus proche à la plus éloignée
        nearest = {
            key: np.argsort(distances_km(lat, lon, latitudes, longitudes))[:MAX_CANDIDATES]
            for key, (lat, lon, _) in locations.items()
        }

        loaded = set()  # stations dont les relevés sont déjà lus
        without_data = set()  # stations sans aucun relevé sur la période
        report_tables = []
        while True:
            chosen = {
                key: self._first_stations(stations, indices, without_data, number_of_stations)
                for key, indices in nearest.items()
            }
            to_load = {s.id for selection in chosen.values() for s in selection} - loaded
            if not to_load:
                break
            # Une requête pour toutes les nouvelles stations ; celles qui n'ont rien sur la
            # période sont écartées et remplacées au tour suivant par les suivantes
            reports = self.report_dao.get_reports_dataframe(sorted(to_load), start_date, end_date)
            report_tables.append(reports)
            loaded |= to_load
            without_data |= to_load - set(reports["station_id"])

        if not report_tables:
            return chosen, pd.DataFrame(columns=REPORT_COLUMNS)
        return chosen, pd.concat(report_tables, ignore_index=True)

    @staticmethod
    def _first_stations(stations, indices, without_data, number_of_stations) -> list[MeteoStation]:
        """Les number_of_stations premières stations de la liste triée, sauf celles sans données."""
        selection = []
        for i in indices:
            if stations[i].id not in without_data:
                selection.append(stations[i])
                if len(selection) == number_of_stations:
                    break
        return selection

    def estimate_daily_temperatures(
        self, locations: Locations, stations_by_location: dict[str, list[MeteoStation]], reports: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Température moyenne estimée de chaque lieu, jour par jour (pondération 1/d²).

        Renvoie deux tableaux avec une ligne par date et une colonne par lieu :
        les températures moyennes (NaN si aucune station n'a de valeur ce jour-là)
        et un booléen vrai si toutes les valeurs utilisées ce jour-là sont observées.
        """
        # Une ligne par date, une colonne par station
        means_by_station = reports.pivot(index="date", columns="station_id", values="temp_mean")
        observed_by_station = reports.pivot(index="date", columns="station_id", values="observed").eq(True)

        means, observed = {}, {}
        for key, (lat, lon, altitude) in locations.items():
            stations = stations_by_location.get(key, [])
            if not stations:
                continue
            ids = [s.id for s in stations]
            values = means_by_station[ids].to_numpy(dtype=float)  # jours x stations

            if altitude is not None:
                # Correction de -0,65 °C par 100 m ; aucune si l'altitude de la station est inconnue
                station_altitudes = np.array(
                    [s.altitude if s.altitude is not None else altitude for s in stations], dtype=float
                )
                values = values - LAPSE_RATE * (altitude - station_altitudes)

            # Poids calculés une seule fois pour toute la période
            distances = distances_km(
                lat, lon, np.array([s.latitude for s in stations]), np.array([s.longitude for s in stations])
            )
            weights = 1 / np.maximum(distances, MIN_DISTANCE_KM) ** 2

            # Chaque jour, seules les stations qui ont une valeur comptent
            has_value = ~np.isnan(values)
            weighted_sum = np.where(has_value, values * weights, 0.0).sum(axis=1)
            weight_total = (has_value * weights).sum(axis=1)
            with np.errstate(invalid="ignore"):
                means[key] = weighted_sum / weight_total  # NaN si aucun poids ce jour-là
            observed[key] = (~has_value | observed_by_station[ids].to_numpy()).all(axis=1)

        index = means_by_station.index
        columns = list(locations)
        means_table = pd.DataFrame(means, index=index).reindex(columns=columns)
        observed_table = pd.DataFrame(observed, index=index).reindex(columns=columns, fill_value=False)
        return means_table, observed_table

    def get_municipality_temperatures(
        self,
        municipalities: list[Municipality],
        start_date: date,
        end_date: date,
        number_of_stations: int = 3,
        use_altitude: bool = True,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Températures moyennes estimées de toutes les communes, une colonne par code INSEE."""
        locations = {
            m.insee_code: (m.latitude, m.longitude, m.altitude if use_altitude else None)
            for m in municipalities
        }
        stations, reports = self.find_candidate_stations(locations, number_of_stations, start_date, end_date)
        return self.estimate_daily_temperatures(locations, stations, reports)
