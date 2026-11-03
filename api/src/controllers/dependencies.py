"""Dépendances d'authentification et traduction des erreurs du service en HTTP."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from business_object.user import User
from service.auth_service import AuthService
from service.errors import SERVICE_ERRORS, ServiceError

bearer = HTTPBearer(auto_error=False)


def http_error(exc: ServiceError) -> HTTPException:
    """Transforme une ServiceError en HTTPException."""
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def user_from_token(token: str) -> User:
    """Renvoie l'utilisateur du jeton, ou lève une erreur HTTP."""
    try:
        return AuthService().get_current_user(token)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User | None:
    """Renvoie l'utilisateur si un jeton est envoyé, sinon None."""
    if credentials is None:
        return None
    return user_from_token(credentials.credentials)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    """Exige un jeton et renvoie l'utilisateur correspondant (401 sinon)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentification requise")
    return user_from_token(credentials.credentials)
