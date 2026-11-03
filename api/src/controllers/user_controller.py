"""Routes d'inscription et de connexion, montées sous /user."""

from fastapi import APIRouter

from controllers.dependencies import SERVICE_ERRORS, http_error
from schema.user_schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from service.auth_service import AuthService

router = APIRouter()
service = AuthService()


@router.post("/register", response_model=UserResponse, status_code=201)
def register(request: RegisterRequest):
    """Crée un compte (409 si le nom est pris)."""
    try:
        user = service.register(request.username, request.password)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return UserResponse(id=user.id, username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """Vérifie les identifiants et renvoie un jeton JWT (401 sinon)."""
    try:
        token = service.authenticate(request.username, request.password)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return TokenResponse(access_token=token)
