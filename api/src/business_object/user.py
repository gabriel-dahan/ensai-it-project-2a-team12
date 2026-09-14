import bcrypt

from api.src.business_object.dju import DjuCalculation
from api.src.business_object.geo_zone import Zoning


class User:

    def __init__(self, username: str, password: str, id=None) -> None:
        self.username = username
        self.__id = id
        self.__zonings: list[Zoning] = []
        self.__calculations: list[DjuCalculation] = []

        salt = bcrypt.gensalt()
        self.__password = bcrypt.hashpw(password.encode("utf-8"), salt)

    @property
    def id(self):
        return self.__id

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