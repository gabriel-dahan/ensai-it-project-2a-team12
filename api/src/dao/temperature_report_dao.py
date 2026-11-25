from datetime import date

import pandas as pd

from dao.db_connection import DBConnection
from utils.singleton import Singleton

REPORT_COLUMNS = ["station_id", "date", "temp_mean", "observed"]


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

    def get_reports_dataframe(
        self, station_ids: list[int], start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Renvoie en une requête les relevés de plusieurs stations sur la période.

        Une ligne par station et par jour, seulement les jours qui ont Tmin et Tmax :
        colonnes station_id, date, temp_mean = (Tmin + Tmax) / 2 et observed
        (False si Tmin ou Tmax a été comblé par qualite_meteo.py).
        """
        if not station_ids:
            return pd.DataFrame(columns=REPORT_COLUMNS)

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT station_id, date,
                           (temp_min + temp_max) / 2 AS temp_mean,
                           COALESCE(source_tmin, 'observee') = 'observee'
                               AND COALESCE(source_tmax, 'observee') = 'observee' AS observed
                    FROM temperature_reports
                    WHERE station_id = ANY(%s) AND date BETWEEN %s AND %s
                      AND temp_min IS NOT NULL AND temp_max IS NOT NULL
                    """,
                    (list(station_ids), start_date, end_date),
                )
                rows = cursor.fetchall()

        return pd.DataFrame(rows, columns=REPORT_COLUMNS)
