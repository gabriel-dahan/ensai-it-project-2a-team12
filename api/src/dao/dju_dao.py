from datetime import date

from psycopg2.extras import execute_values

from business_object.dju import DjuCalculation, DjuResult
from dao.db_connection import DBConnection
from utils.singleton import Singleton


class DjuDao(metaclass=Singleton):
    """Accès aux types de DJU et aux calculs DJU enregistrés (cache)."""

    def get_or_create_dju_type(self, mode: str, threshold: float) -> int:
        """Renvoie l'id du type de DJU (mode, seuil), en le créant si besoin."""
        if mode not in ("heating", "cooling"):
            raise ValueError("Mode de DJU invalide")

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO dju_types (name, mode, base_temperature) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT (mode, base_temperature) DO UPDATE SET name = EXCLUDED.name "
                    "RETURNING id",
                    (mode, mode, threshold),
                )
                result = cursor.fetchone()

        return result["id"]

    def find_calculation(
        self,
        zone_type: str,
        zone_id: int,
        dju_type_id: int,
        start_date: date,
        end_date: date,
        time_step: str,
        number_of_stations: int,
        use_altitude: bool,
    ) -> int | None:
        """Renvoie l'id du dernier calcul enregistré avec ces paramètres, ou None."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM dju_calculations
                    WHERE zone_type = %s
                      AND zone_id = %s
                      AND dju_type_id = %s
                      AND start_date = %s
                      AND end_date = %s
                      AND time_step = %s
                      AND number_of_stations = %s
                      AND use_altitude = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        zone_type,
                        zone_id,
                        dju_type_id,
                        start_date,
                        end_date,
                        time_step,
                        number_of_stations,
                        use_altitude,
                    ),
                )
                result = cursor.fetchone()

        return result["id"] if result else None

    def get_calculation_results(self, calculation_id: int) -> list[DjuResult]:
        """Renvoie les résultats d'un calcul, triés par début de période."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, period_start, period_end, value, days_with_data, observed_ratio "
                    "FROM dju_results WHERE calculation_id = %s ORDER BY period_start",
                    (calculation_id,),
                )
                rows = cursor.fetchall()

        return [
            DjuResult(
                id=row["id"],
                period_start=row["period_start"],
                period_end=row["period_end"],
                value=row["value"],
                days_with_data=row["days_with_data"],
                observed_ratio=row["observed_ratio"],
            )
            for row in rows
        ]

    def save_calculation(self, calculation: DjuCalculation) -> int:
        """Enregistre un calcul sur zone et ses résultats ; renvoie l'id du calcul."""
        if calculation.zone is None or calculation.zone.id is None:
            raise ValueError("Seuls les calculs sur une zone enregistrée peuvent être stockés")
        if calculation.type.id is None:
            raise ValueError("Le type de DJU doit avoir un identifiant")
        if not calculation.results:
            raise ValueError("Impossible d'enregistrer un calcul sans résultats")

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dju_calculations (
                        dju_type_id, zone_type, zone_id, start_date, end_date,
                        time_step, number_of_stations, use_altitude, computed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        calculation.type.id,
                        calculation.zone.zone_type,
                        calculation.zone.id,
                        calculation.start_date,
                        calculation.end_date,
                        calculation.time_step,
                        calculation.number_of_stations,
                        calculation.use_altitude,
                        calculation.computed_at or date.today(),
                    ),
                )
                calculation_id = cursor.fetchone()["id"]

                # Une seule requête pour tous les résultats ; les ids reviennent dans l'ordre
                rows = execute_values(
                    cursor,
                    "INSERT INTO dju_results (calculation_id, period_start, period_end, "
                    "value, days_with_data, observed_ratio) VALUES %s RETURNING id",
                    [
                        (
                            calculation_id,
                            r.period_start,
                            r.period_end,
                            r.value,
                            r.days_with_data,
                            r.observed_ratio,
                        )
                        for r in calculation.results
                    ],
                    fetch=True,
                )

        for result, row in zip(calculation.results, rows):
            result.id = row["id"]
        calculation.id = calculation_id
        return calculation_id

    def delete_calculations_for_zone(self, zone_type: str, zone_id: int) -> int:
        """Supprime les calculs enregistrés d'une zone ; renvoie leur nombre."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM dju_calculations WHERE zone_type = %s AND zone_id = %s",
                    (zone_type, zone_id),
                )
                deleted_count = cursor.rowcount

        return deleted_count
