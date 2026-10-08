"""
API routes for registration and authentication (F4). Mounted under /user.
"""

from fastapi import APIRouter

from controllers.dependencies import SERVICE_ERRORS, http_error
from schema.user_schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from service.auth_service import AuthService

router = APIRouter()
service = AuthService()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(request: RegisterRequest):
    """
    Create an account.
    """
    try:
        user = service.register(request.username, request.password)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return UserResponse(id=user.id, username=user.username)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Check the credentials and open a session (401 if they are wrong).
    """
    try:
        token = service.authenticate(request.username, request.password)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return TokenResponse(access_token=token)
    