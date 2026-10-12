
from datetime import date

from business_object.dju import DjuCalculation, DjuResult
from dao.db_connection import DBConnection
from utils.singleton import Singleton


class DjuDao(metaclass=Singleton):
    """
    Objet d'accès aux données pour les calculs DJU.

    Cette classe permet d'enregistrer, de rechercher,
    de récupérer et de supprimer les calculs DJU
    ainsi que leurs résultats dans PostgreSQL.
    """

    def get_or_create_dju_type(
        self, mode: str, threshold: float
    ) -> int:
        """
        Recherche un type de DJU existant.

        Si le type n'existe pas, il est créé dans
        la base de données.

        Retourne l'identifiant du type de DJU.
        """

        if mode not in ("heating", "cooling"):
            raise ValueError("Mode de DJU invalide")

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dju_types
                        (name, mode, base_temperature)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (mode, base_temperature)
                    DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
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
        """
        Recherche un calcul DJU déjà enregistré.

        La recherche utilise les paramètres du calcul :
        zone, type de DJU, période, pas temporel,
        nombre de stations et correction d'altitude.

        Retourne l'identifiant du calcul s'il existe,
        sinon retourne None.
        """

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

    def get_calculation_results(
        self, calculation_id: int
    ) -> list[DjuResult]:
        """
        Récupère les résultats associés à un calcul DJU.

        Les résultats sont classés par date de début.

        Chaque ligne récupérée dans la base de données
        est transformée en objet DjuResult.

        Retourne une liste d'objets DjuResult.
        """

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, period_start, period_end, value
                    FROM dju_results
                    WHERE calculation_id = %s
                    ORDER BY period_start
                    """,
                    (calculation_id,),
                )

                rows = cursor.fetchall()

        return [
            DjuResult(
                id=row["id"],
                period_start=row["period_start"],
                period_end=row["period_end"],
                value=row["value"],
            )
            for row in rows
        ]

    def save_calculation(
        self,
        calculation: DjuCalculation,
        number_of_stations: int,
        use_altitude: bool,
    ) -> int:
        """
        Enregistre un calcul DJU et ses résultats.

        Seuls les calculs portant sur une zone
        géographique sont enregistrés dans le cache.

        Le calcul est d'abord enregistré dans la table
        dju_calculations pour obtenir son identifiant.

        Chaque résultat est ensuite enregistré dans
        la table dju_results avec cet identifiant.

        Retourne l'identifiant du calcul enregistré.
        """

        if calculation.zone is None:
            raise ValueError(
                "Seuls les calculs par zone peuvent être enregistrés"
            )

        if calculation.zone.id is None:
            raise ValueError(
                "La zone doit posséder un identifiant"
            )

        if calculation.type.id is None:
            raise ValueError(
                "Le type de DJU doit posséder un identifiant"
            )

        if not calculation.results:
            raise ValueError(
                "Impossible d'enregistrer un calcul sans résultats"
            )

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dju_calculations (
                        dju_type_id,
                        zone_type,
                        zone_id,
                        start_date,
                        end_date,
                        time_step,
                        number_of_stations,
                        use_altitude,
                        computed_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        calculation.type.id,
                        calculation.zone.zone_type,
                        calculation.zone.id,
                        calculation.start_date,
                        calculation.end_date,
                        calculation.time_step,
                        number_of_stations,
                        use_altitude,
                        calculation.computed_at or date.today(),
                    ),
                )

                calculation_id = cursor.fetchone()["id"]

                for result in calculation.results:
                    cursor.execute(
                        """
                        INSERT INTO dju_results (
                            calculation_id,
                            period_start,
                            period_end,
                            value
                        )
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            calculation_id,
                            result.period_start,
                            result.period_end,
                            result.value,
                        ),
                    )

                    result.id = cursor.fetchone()["id"]

        calculation.id = calculation_id
        return calculation_id

    def delete_calculations_for_zone(
        self, zone_type: str, zone_id: int
    ) -> int:
        """
        Supprime les calculs DJU enregistrés pour une zone.

        Cette méthode est utile lorsqu'un zonage
        personnalisé est modifié ou supprimé.

        Retourne le nombre de calculs supprimés.
        """

        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM dju_calculations
                    WHERE zone_type = %s
                      AND zone_id = %s
                    """,
                    (zone_type, zone_id),
                )

                deleted_count = cursor.rowcount

        return deleted_count
