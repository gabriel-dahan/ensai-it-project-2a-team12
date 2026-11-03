"""Utilisateur de l'API."""

import bcrypt

from .geo_zone import Zoning


class User:
    def __init__(self, username: str, password: str, id: int | None = None) -> None:
        """Crée un utilisateur et hache son mot de passe avec bcrypt."""
        self.username = username
        self.__id = id
        self.__password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    @classmethod
    def from_storage(cls, user_id: int, username: str, password_hash: str | bytes) -> "User":
        """Recrée un utilisateur lu en base, sans hacher une seconde fois."""
        user = cls.__new__(cls)
        user.username = username
        user.__id = user_id
        if isinstance(password_hash, str):
            password_hash = password_hash.encode("utf-8")
        user.__password = bytes(password_hash)
        return user

    @property
    def id(self) -> int | None:
        return self.__id

    @id.setter
    def id(self, user_id: int) -> None:
        self.__id = user_id

    @property
    def password_hash(self) -> str:
        """Hash bcrypt enregistré en base."""
        return self.__password.decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.__password)

    def create_zoning(self, name: str, description: str | None = None) -> Zoning:
        """Nouveau zonage (vide) appartenant à cet utilisateur."""
        return Zoning(id=None, name=name, description=description, owner_id=self.id)
