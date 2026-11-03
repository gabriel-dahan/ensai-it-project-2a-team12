from datetime import date

from business_object.temperature_report import TemperatureReport
from dao.db_connection import DBConnection
from utils.singleton import Singleton

COLUMNS = "id, station_id, date, temp_min, temp_max, source_tmin, source_tmax"


class TemperatureReportDao(metaclass=Singleton):
    """Accès aux relevés quotidiens des stations."""

    def __init__(self):
        self._date_range = None

    def get_date_range(self) -> tuple[date | None, date | None]:
        """Renvoie la première et la dernière date des relevés, lues en base une seule fois."""
        if self._date_range is None:
            with DBConnection().connection as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT MIN(date) AS first_date, MAX(date) AS last_date "
                        "FROM temperature_reports"
                    )
                    row = cursor.fetchone()
            self._date_range = (row["first_date"], row["last_date"])
        return self._date_range

    def get_reports_by_station_and_date_range(
        self, station_id: int, start_date: date, end_date: date
    ) -> list[TemperatureReport]:
        """Renvoie les relevés d'une station sur la période, triés par date."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {COLUMNS} FROM temperature_reports "
                    "WHERE station_id = %s AND date BETWEEN %s AND %s "
                    "ORDER BY date",
                    (station_id, start_date, end_date),
                )
                rows = cursor.fetchall()

        return [self._to_report(row) for row in rows]

    def get_reports_for_stations(
        self, station_ids: list[int], start_date: date, end_date: date
    ) -> dict[int, list[TemperatureReport]]:
        """Renvoie les relevés de plusieurs stations en une requête : {station_id: relevés}."""
        reports = {station_id: [] for station_id in station_ids}
        if not station_ids:
            return reports

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {COLUMNS} FROM temperature_reports "
                    "WHERE station_id = ANY(%s) AND date BETWEEN %s AND %s "
                    "ORDER BY station_id, date",
                    (list(station_ids), start_date, end_date),
                )
                rows = cursor.fetchall()

        for row in rows:
            reports.setdefault(row["station_id"], []).append(self._to_report(row))
        return reports

    def get_stations_with_reports(
        self, station_ids: list[int], start_date: date, end_date: date
    ) -> set[int]:
        """Renvoie les ids des stations ayant au moins une température sur la période."""
        if not station_ids:
            return set()

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT DISTINCT station_id FROM temperature_reports "
                    "WHERE station_id = ANY(%s) AND date BETWEEN %s AND %s "
                    "AND (temp_min IS NOT NULL OR temp_max IS NOT NULL)",
                    (list(station_ids), start_date, end_date),
                )
                rows = cursor.fetchall()

        return {row["station_id"] for row in rows}

    @staticmethod
    def _to_report(row: dict) -> TemperatureReport:
        """Transforme une ligne en TemperatureReport."""
        observed = row["source_tmin"] in (None, "observee") and row["source_tmax"] in (None, "observee")
        return TemperatureReport(
            id=row["id"],
            station_id=row["station_id"],
            date=row["date"],
            temp_min=row["temp_min"],
            temp_max=row["temp_max"],
            observed=observed,
        )
