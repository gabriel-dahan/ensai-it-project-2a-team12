from datetime import date

from psycopg2.extras import execute_values

from business_object.temperature_report import TemperatureReport
from dao.db_connection import DBConnection
from utils.singleton import Singleton


class MunicipalityTemperatureDao(metaclass=Singleton):
    """Accès au cache des températures estimées par commune."""

    def get_temperatures(
        self, municipality_id: int, start_date: date, end_date: date
    ) -> list[TemperatureReport]:
        """Renvoie les températures stockées d'une commune sur la période, triées par date."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT date, temp_min, temp_max, observed FROM municipality_temperatures "
                    "WHERE municipality_id = %s AND date BETWEEN %s AND %s "
                    "ORDER BY date",
                    (municipality_id, start_date, end_date),
                )
                rows = cursor.fetchall()

        return [
            TemperatureReport(
                station_id=None,
                date=row["date"],
                temp_min=row["temp_min"],
                temp_max=row["temp_max"],
                observed=bool(row["observed"]),
            )
            for row in rows
        ]

    def save_temperatures(self, municipality_id: int, reports: list[TemperatureReport]) -> None:
        """Enregistre les températures d'une commune (les jours déjà stockés sont ignorés)."""
        if not reports:
            return

        rows = [
            (municipality_id, r.date, r.temp_min, r.temp_max, r.observed)
            for r in reports
        ]
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                execute_values(
                    cursor,
                    "INSERT INTO municipality_temperatures "
                    "(municipality_id, date, temp_min, temp_max, observed) VALUES %s "
                    "ON CONFLICT DO NOTHING",
                    rows,
                )
