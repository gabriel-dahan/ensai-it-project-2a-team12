"""Inscription, connexion et jetons JWT."""

import os
from datetime import UTC, datetime, timedelta

import jwt

from business_object.user import User
from dao.user_dao import UserDao
from service.errors import ServiceError

TOKEN_LIFETIME = timedelta(hours=24)
ALGORITHM = "HS256"


class AuthService:
    """Gestion des comptes et des jetons d'accès."""

    def __init__(self, user_dao=None):
        self.user_dao = user_dao or UserDao()

    def register(self, username: str, password: str) -> User:
        """Crée un compte ; 409 si le nom est déjà pris."""
        if self.user_dao.find_by_username(username) is not None:
            raise ServiceError("Ce nom d'utilisateur est déjà pris.", 409)
        user = self.user_dao.create(User(username=username, password=password))
        if user is None:
            raise ServiceError("Ce nom d'utilisateur est déjà pris.", 409)
        return user

    def authenticate(self, username: str, password: str) -> str:
        """Vérifie les identifiants et renvoie un jeton valable 24 h ; 401 sinon."""
        user = self.user_dao.find_by_username(username)
        if user is None or not user.check_password(password):
            raise ServiceError("Nom d'utilisateur ou mot de passe incorrect.", 401)
        payload = {"sub": str(user.id), "exp": datetime.now(UTC) + TOKEN_LIFETIME}
        return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=ALGORITHM)

    def get_current_user(self, token: str) -> User:
        """Renvoie l'utilisateur du jeton ; 401 si le jeton est invalide ou expiré."""
        try:
            payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[ALGORITHM])
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise ServiceError("Jeton invalide ou expiré.", 401) from None
        user = self.user_dao.find_by_id(user_id)
        if user is None:
            raise ServiceError("Jeton invalide ou expiré.", 401)
        return user
