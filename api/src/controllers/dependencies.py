"""Authentication dependencies and HTTP translation of service errors."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from business_object.user import User
from service.errors import SERVICE_ERRORS, ServiceError

_bearer = HTTPBearer(auto_error=False)


def http_error(exc: ServiceError) -> HTTPException:
    """Turn a service error into the HTTP response expected by the controllers."""
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _user_from_token(token: str) -> User:
    from service.auth_service import AuthService

    try:
        return AuthService().get_current_user(token)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User | None:
    """Return the caller when a bearer token is sent, otherwise None."""
    if credentials is None:
        return None
    return _user_from_token(credentials.credentials)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Require a bearer token and return the corresponding user."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return _user_from_token(credentials.credentials)
