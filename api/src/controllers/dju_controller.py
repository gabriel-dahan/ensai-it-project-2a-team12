"""
API routes for DJU calculations (F1, F3).
"""

from fastapi import APIRouter, Depends

from business_object.dju import DjuCalculation
from business_object.user import User
from controllers.dependencies import SERVICE_ERRORS, get_optional_user, http_error
from schema.dju_schema import DjuPointRequest, DjuResponse, DjuResultItem, DjuZoneRequest
from service.dju_service import DjuService

router = APIRouter()
service = DjuService()


def _to_response(calculations: dict[str, DjuCalculation]) -> DjuResponse:
    return DjuResponse(
        calculation_ids={mode: calc.id for mode, calc in calculations.items()},
        results={
            mode: [
                DjuResultItem(period_start=r.period_start, period_end=r.period_end, value=r.value)
                for r in calc.results
            ]
            for mode, calc in calculations.items()
        },
    )


@router.get("/")
async def get_dju_info():
    """
    Check that the DJU routes are available.
    """
    return {"message": "DJU routes are available"}


@router.post("/point", response_model=DjuResponse)
async def calculate_point_dju(
    request: DjuPointRequest,
    user: User | None = Depends(get_optional_user),
):
    """
    F1 - DJU for a geographic point. Authentication is optional: it only
    attaches the calculation to the caller's history.
    """
    try:
        return _to_response(service.calculate_point_dju(request, user))
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


@router.post("/zone", response_model=DjuResponse)
async def compute_zone_dju(
    request: DjuZoneRequest,
    user: User | None = Depends(get_optional_user),
):
    """
    F3 - DJU for a department, a region or a personal zoning. Official zones
    are public; a personal zoning requires its owner (401 / 403 otherwise).
    """
    try:
        return _to_response(service.calculate_zone_dju(request, user))
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc