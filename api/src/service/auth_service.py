"""Registration and authentication."""

from typing import NoReturn

from service.errors import NotImplementedFeature


class AuthService:
    """Accounts and access tokens. The behaviour is not implemented yet."""

    def register(self, username: str, password: str) -> NoReturn:
        """Create an account."""
        raise NotImplementedFeature("User registration is not implemented yet.")

    def authenticate(self, username: str, password: str) -> NoReturn:
        """Check credentials and return an access token."""
        raise NotImplementedFeature("Login is not implemented yet.")

    def get_current_user(self, token: str) -> NoReturn:
        """Resolve a bearer token to the user who owns it."""
        raise NotImplementedFeature("Token authentication is not implemented yet.")
