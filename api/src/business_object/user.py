import bcrypt

from api.src.business_object.dju import DjuCalculation
from api.src.business_object.geo_zone import Zoning


class User:

    def __init__(self, username: str, password: str, id=None) -> None:
        self.username = username
        self.__id = id

        salt = bcrypt.gensalt()
        self.__password = bcrypt.hashpw(password, salt)

    def check_password(self, tried_password: str) -> bool:
        return bcrypt.checkpw(tried_password, self.__password)

    def create_zoning(self, description: str) -> Zoning:
        ...

    def get_calculations(self) -> list[DjuCalculation]:
        ...