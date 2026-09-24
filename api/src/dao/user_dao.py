import psycopg2

from business_object.user import User
from dao.db_connection import DBConnection
from utils.singleton import Singleton


class UserDao(metaclass=Singleton):
    """Data Access Object for User
    """

    def find_by_id(self, user_id: int) -> User | None:
        """Return the user with this id, or None."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password FROM users WHERE id = %s",
                    (user_id,),
                )
                res = cursor.fetchone()

        return self._to_user(res) if res else None

    def find_by_username(self, username: str) -> User | None:
        """Return the user with this username, or None."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password FROM users WHERE username = %s",
                    (username,),
                )
                res = cursor.fetchone()

        return self._to_user(res) if res else None

    def create(self, user: User) -> User | None:
        """Insert a user and set its id. Returns None if the username exists."""
        if user.id is not None:
            raise ValueError("User already has an id; use update() instead")

        try:
            with DBConnection().connection as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (username, password) VALUES (%s, %s) "
                        "RETURNING id",
                        (user.username, user.password_hash),
                    )
                    res = cursor.fetchone()
        except psycopg2.IntegrityError:
            return None

        if not res:
            return None

        user.id = res["id"]
        return user

    def update(self, user: User) -> bool:
        """Update username and password. Returns True if a row was updated."""
        if user.id is None:
            return False

        try:
            with DBConnection().connection as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE users SET username = %s, password = %s WHERE id = %s",
                        (user.username, user.password_hash, user.id),
                    )
                    updated = cursor.rowcount == 1
        except psycopg2.IntegrityError:
            return False

        return updated

    def delete(self, user_id: int) -> bool:
        """Delete the user with this id. Returns True if a row was deleted."""
        with DBConnection().connection as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                deleted = cursor.rowcount == 1

        return deleted

    @staticmethod
    def _to_user(row: dict) -> User:
        return User.from_storage(row["id"], row["username"], row["password"])
