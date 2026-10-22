"""Errors raised by the service layer and translated into HTTP responses."""


class ServiceError(Exception):
    """Business error carrying the HTTP status the controller should return."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class NotImplementedFeature(ServiceError):
    """The route exists, but the business logic is not available yet."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=501)


SERVICE_ERRORS = (ServiceError,)
