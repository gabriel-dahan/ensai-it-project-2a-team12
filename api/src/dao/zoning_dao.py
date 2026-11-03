from datetime import date

from business_object.geo_zone import Zoning
from dao.db_connection import DBConnection
from dao.geo_zone_dao import MUNICIPALITY_COLUMNS, municipality_from_row
from utils.singleton import Singleton


class ZoningDao(metaclass=Singleton):
    """Accès aux zonages personnalisés et à leurs communes."""

    def create(self, zoning: Zoning) -> Zoning:
        """Enregistre le zonage et ses communes, puis renseigne zoning.id."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO zonings (name, description, created_at, user_id) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (zoning.name, zoning.description, zoning.created_at or date.today(), zoning.owner_id),
                )
                zoning.id = cursor.fetchone()["id"]
                self._insert_links(cursor, zoning)
        return zoning

    def find_by_id(self, zoning_id: int) -> Zoning | None:
        """Renvoie le zonage avec ses communes, ou None."""
        zonings = self._find("WHERE id = %s", (zoning_id,))
        return zonings[0] if zonings else None

    def find_by_user(self, user_id: int) -> list[Zoning]:
        """Renvoie les zonages d'un utilisateur, avec leurs communes."""
        return self._find("WHERE user_id = %s", (user_id,))

    def update(self, zoning: Zoning) -> None:
        """Met à jour le nom, la description et remplace les communes du zonage."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE zonings SET name = %s, description = %s WHERE id = %s",
                    (zoning.name, zoning.description, zoning.id),
                )
                cursor.execute("DELETE FROM zoning_municipalities WHERE zoning_id = %s", (zoning.id,))
                self._insert_links(cursor, zoning)

    def delete(self, zoning_id: int) -> bool:
        """Supprime le zonage (ses liens partent en cascade). True si une ligne a été supprimée."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM zonings WHERE id = %s", (zoning_id,))
                deleted = cursor.rowcount == 1
        return deleted

    @staticmethod
    def _insert_links(cursor, zoning: Zoning) -> None:
        """Lie le zonage à ses communes (retrouvées par code INSEE)."""
        codes = [m.insee_code for m in zoning.municipalities]
        if codes:
            cursor.execute(
                "INSERT INTO zoning_municipalities (zoning_id, municipality_id) "
                "SELECT %s, id FROM municipalities WHERE insee_code = ANY(%s) "
                "ON CONFLICT DO NOTHING",
                (zoning.id, codes),
            )

    @staticmethod
    def _find(where: str, params: tuple) -> list[Zoning]:
        """Lit des zonages (filtre `where`) puis leurs communes en une requête."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT id, name, description, created_at, user_id FROM zonings {where} ORDER BY id",
                    params,
                )
                zoning_rows = cursor.fetchall()
                if not zoning_rows:
                    return []

                zonings = {
                    row["id"]: Zoning(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        created_at=row["created_at"],
                        owner_id=row["user_id"],
                    )
                    for row in zoning_rows
                }
                cursor.execute(
                    f"SELECT zm.zoning_id, {MUNICIPALITY_COLUMNS} FROM zoning_municipalities zm "
                    "JOIN municipalities m ON m.id = zm.municipality_id "
                    "WHERE zm.zoning_id = ANY(%s) ORDER BY m.insee_code",
                    (list(zonings),),
                )
                municipality_rows = cursor.fetchall()

        for row in municipality_rows:
            zonings[row["zoning_id"]].municipalities.append(municipality_from_row(row))
        return list(zonings.values())
