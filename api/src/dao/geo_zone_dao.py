from dao.db_connection import DBConnection
from business_object.geo_zone import Municipality
from utils.singleton import Singleton


class GeoZoneDao(metaclass=Singleton):
    """
    Data Access Object for Geographic Zones.

    This class handles the retrieval and management of the geographical hierarchy
    (Municipalities, Departments, Regions) and user-defined Zoning objects.
    """

    def get_municipality_by_insee(self, insee_code: str) -> Municipality | None:
        """
        Retrieves a municipality by its INSEE code.

        Args:
            insee_code (str): The unique INSEE code of the municipality.

        Returns:
            Municipality | None: The Municipality object if found, otherwise None.
        """
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, insee_code, name, latitude, longitude, altitude, population "
                    "FROM municipalities WHERE insee_code = %s",
                    (insee_code,)
                )
                res = cursor.fetchone()

        if res:
            return Municipality(
                id=res["id"],
                insee_code=res["insee_code"],
                name=res["name"],
                latitude=res["latitude"],
                longitude=res["longitude"],
                altitude=res["altitude"],
                population=res["population"]
            )
        return None

    def get_municipalities_by_department(self, department_id: int) -> list[Municipality]:
        """
        Retrieves all municipalities belonging to a specific department.

        Args:
            department_id (int): The ID of the department.

        Returns:
            List[Municipality]: A list of Municipality objects.
        """
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, insee_code, name, latitude, longitude, altitude, population "
                    "FROM municipalities WHERE department_id = %s",
                    (department_id,)
                )
                res = cursor.fetchall()

        if res:
            return [
                Municipality(
                    id=row["id"],
                    insee_code=row["insee_code"],
                    name=row["name"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    altitude=row["altitude"],
                    population=row["population"]
                )
                for row in res
            ]
        return []
