"""Erreurs de la couche service, traduites en réponses HTTP par les contrôleurs."""


class ServiceError(Exception):
    """Erreur métier avec le code HTTP à renvoyer."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


SERVICE_ERRORS = (ServiceError,)
