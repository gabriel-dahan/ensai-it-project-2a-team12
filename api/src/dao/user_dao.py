"""DAO des comptes utilisateurs."""

import psycopg2

from business_object.user import User
from dao.db_connection import DBConnection
from utils.singleton import Singleton


class UserDao(metaclass=Singleton):
    """Accès aux comptes utilisateurs."""

    def find_by_id(self, user_id: int) -> User | None:
        """Renvoie l'utilisateur de cet id, ou None."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password FROM users WHERE id = %s",
                    (user_id,),
                )
                res = cursor.fetchone()

        return self._to_user(res) if res else None

    def find_by_username(self, username: str) -> User | None:
        """Renvoie l'utilisateur de ce nom, ou None."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password FROM users WHERE username = %s",
                    (username,),
                )
                res = cursor.fetchone()

        return self._to_user(res) if res else None

    def create(self, user: User) -> User | None:
        """Enregistre l'utilisateur et renseigne son id ; None si le nom est déjà pris."""
        if user.id is not None:
            raise ValueError("L'utilisateur est déjà enregistré")

        try:
            with DBConnection().connection as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id",
                        (user.username, user.password_hash),
                    )
                    res = cursor.fetchone()
        except psycopg2.IntegrityError:
            return None

        if not res:
            return None

        user.id = res["id"]
        return user

    @staticmethod
    def _to_user(row: dict) -> User:
        """Transforme une ligne en User."""
        return User.from_storage(
            user_id=row["id"], username=row["username"], password_hash=row["password"]
        )
