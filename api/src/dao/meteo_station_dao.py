from business_object.geo_zone import haversine_km
from business_object.meteo_station import MeteoStation
from dao.db_connection import DBConnection
from utils.singleton import Singleton


class MeteoStationDao(metaclass=Singleton):
    """Accès aux stations météo (gardées en mémoire après le premier chargement)."""

    def __init__(self):
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

    def get_station_by_id(self, station_id: int) -> MeteoStation | None:
        """Renvoie la station de cet id, ou None."""
        for station in self.get_all_stations():
            if station.id == station_id:
                return station
        return None

    def get_station_by_code(self, station_code: str) -> MeteoStation | None:
        """Renvoie la station de ce code, ou None."""
        for station in self.get_all_stations():
            if station.station_code == station_code:
                return station
        return None

    def find_nearest_stations(self, lat: float, lon: float, limit: int = 3) -> list[MeteoStation]:
        """Renvoie les `limit` stations les plus proches du point."""
        stations = self.get_all_stations()
        stations.sort(key=lambda s: haversine_km(lat, lon, s.latitude, s.longitude))
        return stations[:limit]
