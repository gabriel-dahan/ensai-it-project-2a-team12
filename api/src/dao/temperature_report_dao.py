from dao.db_connection import DBConnection
from business_object.temperature_report import TemperatureReport
from utils.singleton import Singleton


class TemperatureReportDao(metaclass=Singleton):
    """
    Data Access Object for TemperatureReport.

    This class handles all database operations related to temperature measurements,
    focusing on retrieving historical data for DJU calculations.
    """

    def get_reports_by_station_and_date_range(self, station_id: int, start_date: str, end_date: str) -> list[TemperatureReport]:
        """
        Retrieves all temperature reports for a specific station within a date range.
        This is the primary method used for DJU calculations.

        Args:
            station_id (int): The ID of the weather station.
            start_date (str): The start date in 'YYYY-MM-DD' format.
            end_date (str): The end date in 'YYYY-MM-DD' format.

        Returns:
            List[TemperatureReport]: A list of TemperatureReport objects.
        """
        # Step 1: We get the connection using the DBConnection class.
        with DBConnection().connection as connection:
            # Step 2: From the connection, we create a cursor for the query.
            with connection.cursor() as cursor:
                # Step 3: We execute our SQL query with parameters to prevent injection.
                query = """
                    SELECT id, station_id, date, temp_min, temp_max, temp_mean 
                    FROM temperature_reports 
                    WHERE station_id = %s AND date BETWEEN %s AND %s
                    ORDER BY date ASC
                """
                cursor.execute(query, (station_id, start_date, end_date))

                # Step 4: We store the query result.
                res = cursor.fetchall()

        if res:
            # Step 5: We format the results into the desired shape (list of TemperatureReport objects).
            return [
                TemperatureReport(
                    id=row["id"],
                    station_id=row["station_id"],
                    date=row["date"],
                    temp_min=row["temp_min"],
                    temp_max=row["temp_max"],
                    temp_mean=row["temp_mean"]
                )
                for row in res
            ]
        return []

    def get_latest_report_for_station(self, station_id: int) -> TemperatureReport | None:
        """
        Retrieves the most recent temperature report for a given station.

        Args:
            station_id (int): The ID of the weather station.

        Returns:
            TemperatureReport | None: The latest report if found, otherwise None.
        """
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, station_id, date, temp_min, temp_max, temp_mean "
                    "FROM temperature_reports WHERE station_id = %s "
                    "ORDER BY date DESC LIMIT 1",
                    (station_id,)
                )
                res = cursor.fetchone()

        if res:
            return TemperatureReport(
                id=res["id"],
                station_id=res["station_id"],
                date=res["date"],
                temp_min=res["temp_min"],
                temp_max=res["temp_max"],
                temp_mean=res["temp_mean"]
            )
        return None