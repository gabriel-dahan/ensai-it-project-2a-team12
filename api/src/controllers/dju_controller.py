"""
API routes for DJU calculations.
"""

from fastapi import APIRouter

from schema.dju_schema import DjuPointRequest


router = APIRouter()


@router.get("/")
async def get_dju_info():
    """
    Check that the DJU routes are available.
    """
    return {
        "message": "DJU routes are available"
    }


@router.post("/point")
async def calculate_point_dju(request: DjuPointRequest):
    """
    Receive the parameters required to calculate DJU for a geographic point.

    The actual DJU calculation will be implemented in the service layer.
    """

    return {
        "message": "DJU point request received",
        "parameters": request.model_dump(),
    }