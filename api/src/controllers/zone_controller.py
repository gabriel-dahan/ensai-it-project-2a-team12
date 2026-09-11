"""
API routes for zones creation and management.
"""

from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def get_created_zones():
    ...

@router.post("/create")
async def create_personalized_zoning():
    ...