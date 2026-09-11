"""
API routes for user-specific features.
"""

from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def get_current_user():
    ...

@router.post("/login")
async def user_login():
    ...