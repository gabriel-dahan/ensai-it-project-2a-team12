import bcrypt

from .dju import DjuCalculation
from .geo_zone import Zoning


class User:

    def __init__(self, username: str, password: str, id=None) -> None:
        self.username = username
        self.__id = id
        self.__zonings: list[Zoning] = []
        self.__calculations: list[DjuCalculation] = []

        salt = bcrypt.gensalt()
        self.__password = bcrypt.hashpw(password.encode("utf-8"), salt)

    @classmethod
    def from_storage(cls, user_id: int, username: str, password_hash: str | bytes) -> "User":
        """Rebuild a user already stored in the database.

        ``User.__init__`` always bcrypt-hashes its password argument. A row
        loaded for login must keep the stored hash, otherwise
        ``check_password`` can never succeed.
        """
        user = cls.__new__(cls)
        user.username = username
        user.__id = user_id
        user.__zonings = []
        user.__calculations = []
        if isinstance(password_hash, str):
            password_hash = password_hash.encode("utf-8")
        else:
            password_hash = bytes(password_hash)
        user.__password = password_hash
        return user

    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, user_id: int) -> None:
        self.__id = user_id

    @property
    def password_hash(self) -> str:
        """Bcrypt hash persisted in the ``users`` table. The plain password stays private."""
        hashed = self.__password
        if isinstance(hashed, bytes):
            return hashed.decode("utf-8")
        return hashed

    def check_password(self, tried_password: str) -> bool:
        return bcrypt.checkpw(tried_password.encode("utf-8"), self.__password)

    def create_zoning(self, description: str) -> Zoning:
        zoning = Zoning(id=None, name=description, description=description, owner=self)
        self.__zonings.append(zoning)
        return zoning

    def get_zonings(self) -> list[Zoning]:
        return list(self.__zonings)

    def get_calculations(self) -> list[DjuCalculation]:
        return list(self.__calculations)

    def add_calculation(self, calculation: DjuCalculation) -> None:
        calculation.owner = self
        self.__calculations.append(calculation)