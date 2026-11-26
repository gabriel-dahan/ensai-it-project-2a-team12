"""DAO des stations météo."""

from business_object.meteo_station import MeteoStation
from dao.db_connection import DBConnection
from utils.singleton import Singleton


class MeteoStationDao(metaclass=Singleton):
    """Accès aux stations météo (gardées en mémoire après le premier chargement)."""

    def __init__(self):
        """Cache des stations, vide jusqu'à la première lecture."""
        self._stations = []

    def get_all_stations(self) -> list[MeteoStation]:
        """Renvoie toutes les stations, lues en base une seule fois."""
        if not self._stations:
            with DBConnection().connection as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id, station_code, name, latitude, longitude, altitude "
                        "FROM meteo_stations ORDER BY id"
                    )
                    rows = cursor.fetchall()

            self._stations = [
                MeteoStation(
                    id=row["id"],
                    station_code=row["station_code"],
                    name=row["name"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    altitude=row["altitude"],
                )
                for row in rows
            ]
        return list(self._stations)
