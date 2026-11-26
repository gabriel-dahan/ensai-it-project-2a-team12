"""Schémas d'inscription et de connexion."""

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    """Corps de POST /user/register."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_max_72_bytes(cls, value: str) -> str:
        """Refuse un mot de passe de plus de 72 octets, limite de bcrypt."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Le mot de passe ne doit pas dépasser 72 octets.")
        return value


class LoginRequest(BaseModel):
    """Corps de POST /user/login."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Jeton JWT renvoyé à la connexion."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Compte créé, sans son mot de passe."""

    id: int | None
    username: str
