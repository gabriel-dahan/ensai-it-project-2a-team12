"""Métaclasse Singleton, utilisée par la connexion à la base et les DAO."""


class Singleton(type):
    """Métaclasse Singleton : une seule instance par classe."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Crée l'instance au premier appel, puis renvoie toujours la même."""
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
