from business_object.geo_zone import Department, Municipality, Region
from dao.db_connection import DBConnection
from utils.singleton import Singleton

MUNICIPALITY_COLUMNS = (
    "m.id, m.insee_code, m.name, m.latitude, m.longitude, "
    "m.altitude, m.population, m.department_id"
)


def municipality_from_row(row: dict) -> Municipality:
    """Transforme une ligne de municipalities en Municipality."""
    return Municipality(
        id=row["id"],
        name=row["name"],
        insee_code=row["insee_code"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        altitude=row["altitude"],
        population=row["population"],
        department_id=row["department_id"],
    )


class GeoZoneDao(metaclass=Singleton):
    """Accès aux régions, départements et communes."""

    def get_regions(self) -> list[Region]:
        """Renvoie toutes les régions (sans départements), triées par code INSEE."""
        rows = self._fetch_all("SELECT id, insee_code, name FROM regions ORDER BY insee_code")
        return [self._to_region(row) for row in rows]

    def get_departments(self) -> list[Department]:
        """Renvoie tous les départements (sans communes), triés par code INSEE."""
        rows = self._fetch_all(
            "SELECT id, insee_code, name, region_id FROM departments ORDER BY insee_code"
        )
        return [self._to_department(row) for row in rows]

    def get_region_by_id(self, region_id: int, with_municipalities: bool = False) -> Region | None:
        """Renvoie la région avec ses départements (et leurs communes si demandé), ou None."""
        rows = self._fetch_all("SELECT id, insee_code, name FROM regions WHERE id = %s", (region_id,))
        if not rows:
            return None
        region = self._to_region(rows[0])

        rows = self._fetch_all(
            "SELECT id, insee_code, name, region_id FROM departments "
            "WHERE region_id = %s ORDER BY insee_code",
            (region_id,),
        )
        departments = {}
        for row in rows:
            department = self._to_department(row)
            departments[department.id] = department
            region.add_department(department)

        if with_municipalities:
            rows = self._fetch_all(
                f"SELECT {MUNICIPALITY_COLUMNS} FROM municipalities m "
                "JOIN departments d ON d.id = m.department_id "
                "WHERE d.region_id = %s ORDER BY m.insee_code",
                (region_id,),
            )
            for row in rows:
                departments[row["department_id"]].add_municipality(municipality_from_row(row))
        return region

    def get_department_by_id(
        self, department_id: int, with_municipalities: bool = False
    ) -> Department | None:
        """Renvoie le département (avec ses communes si demandé), ou None."""
        rows = self._fetch_all(
            "SELECT id, insee_code, name, region_id FROM departments WHERE id = %s",
            (department_id,),
        )
        if not rows:
            return None
        department = self._to_department(rows[0])

        if with_municipalities:
            for municipality in self.get_municipalities_by_department(department_id):
                department.add_municipality(municipality)
        return department

    def get_municipality_by_insee(self, insee_code: str) -> Municipality | None:
        """Renvoie la commune de ce code INSEE, ou None."""
        municipalities = self.get_municipalities_by_insee([insee_code])
        return municipalities[0] if municipalities else None

    def get_municipalities_by_insee(self, codes: list[str]) -> list[Municipality]:
        """Renvoie les communes connues parmi ces codes INSEE (une requête)."""
        if not codes:
            return []
        rows = self._fetch_all(
            f"SELECT {MUNICIPALITY_COLUMNS} FROM municipalities m "
            "WHERE m.insee_code = ANY(%s) ORDER BY m.insee_code",
            (list(codes),),
        )
        return [municipality_from_row(row) for row in rows]

    def get_municipalities_by_department(self, department_id: int) -> list[Municipality]:
        """Renvoie les communes d'un département, triées par code INSEE."""
        rows = self._fetch_all(
            f"SELECT {MUNICIPALITY_COLUMNS} FROM municipalities m "
            "WHERE m.department_id = %s ORDER BY m.insee_code",
            (department_id,),
        )
        return [municipality_from_row(row) for row in rows]

    @staticmethod
    def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
        """Exécute une requête de lecture et renvoie toutes les lignes."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()

    @staticmethod
    def _to_region(row: dict) -> Region:
        return Region(id=row["id"], name=row["name"], insee_code=row["insee_code"])

    @staticmethod
    def _to_department(row: dict) -> Department:
        return Department(
            id=row["id"],
            name=row["name"],
            insee_code=row["insee_code"],
            region_id=row["region_id"],
        )
