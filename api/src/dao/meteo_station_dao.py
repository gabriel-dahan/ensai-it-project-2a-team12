from dao.db_connection import DBConnection
from business_object.meteo_station import MeteoStation
from utils.singleton import Singleton


class MeteoStationDao(metaclass=Singleton):
    """
    Data Access Object for MeteoStation.

    This class handles all database operations related to weather stations,
    including standard CRUD operations and specialized geographical queries
    to support proximity-based business logic.
    """

    def get_all_stations(self) -> list[MeteoStation]:
        """
        Retrieves all weather stations from the database.

        Returns:
            List[MeteoStation]: A list of all MeteoStation objects.
        """
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, station_code, name, latitude, longitude, altitude FROM meteo_stations")

                res = cursor.fetchall()

        if res:
            return [
                MeteoStation(
                    id=row["id"],
                    station_code=row["station_code"],
                    name=row["name"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    altitude=row["altitude"]
                )
                for row in res
            ]
        return []

    def get_station_by_id(self, station_id: int) -> MeteoStation | None:
        """
        Retrieves a specific weather station by its unique ID.

        Args:
            station_id (int): The unique identifier of the station.

        Returns:
            MeteoStation | None: The MeteoStation object if found, otherwise None.
        """
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, station_code, name, latitude, longitude, altitude FROM meteo_stations WHERE id = %s", 
                    (station_id,)
                )
                res = cursor.fetchone()

        if res:
            return MeteoStation(
                id=res["id"],
                station_code=res["station_code"],
                name=res["name"],
                latitude=res["latitude"],
                longitude=res["longitude"],
                altitude=res["altitude"]
            )
        return None

    def get_station_by_code(self, station_code: str) -> MeteoStation | None:
        """
        Retrieves a specific weather station by its station code.

        Args:
            station_code (str): The unique station code.

        Returns:
            MeteoStation | None: The MeteoStation object if found, otherwise None.
        """
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, station_code, name, latitude, longitude, altitude FROM meteo_stations WHERE station_code = %s",
                    (station_code,)
                )
                res = cursor.fetchone()

        if res:
            return MeteoStation(
                id=res["id"],
                station_code=res["station_code"],
                name=res["name"],
                latitude=res["latitude"],
                longitude=res["longitude"],
                altitude=res["altitude"]
            )
        return None

    def find_nearest_stations(self, lat: float, lon: float, limit: int = 3) -> list[MeteoStation]:
        """
        Finds the N nearest weather stations to a given coordinate.

        This is implemented as a Query Method. Currently, it retrieves stations 
        and sorts them using the Haversine formula. In a production environment 
        with PostGIS, this would be optimized into a single SQL query using ST_Distance.

        Args:
            lat (float): Target latitude.
            lon (float): Target longitude.
            limit (int): Maximum number of stations to return. Defaults to 3.

        Returns:
            List[MeteoStation]: A list of the closest MeteoStation objects.
        """
        from business_object.geo_zone import _haversine_km

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, station_code, name, latitude, longitude, altitude FROM meteo_stations")
                res = cursor.fetchall()

        if not res:
            return []

        stations = [
            MeteoStation(
                id=row["id"],
                station_code=row["station_code"],
                name=row["name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                altitude=row["altitude"]
            )
            for row in res
        ]

        # Sort stations based on their distance to the provided coordinates
        stations.sort(key=lambda s: _haversine_km(lat, lon, s.latitude, s.longitude))

        return stations[:limit]

    def find_station_at_coordinate(self, lat: float, lon: float, tolerance_km: float = 1.0) -> MeteoStation | None:
        """
        Finds the single closest station to a specific coordinate within a certain tolerance.

        Args:
            lat (float): Target latitude.
            lon (float): Target longitude.
            tolerance_km (float): Maximum allowed distance in km.

        Returns:
            MeteoStation | None: The closest station if within tolerance, otherwise None.
        """
        from business_object.geo_zone import _haversine_km

        # We reuse the nearest stations logic for efficiency
        nearest = self.find_nearest_stations(lat, lon, limit=1)

        if nearest:
            station = nearest[0]
            distance = _haversine_km(lat, lon, station.latitude, station.longitude)
            if distance <= tolerance_km:
                return station

        return None