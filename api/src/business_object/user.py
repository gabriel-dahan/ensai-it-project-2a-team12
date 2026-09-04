
class User:

    def __init__(self, username: str, password: str, id=None) -> None:
        self.username = username
        self.__password = password
        self.__id = id