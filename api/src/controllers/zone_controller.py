"""
API routes for zones.

Two routers, mounted by the main file:
    router       -> /zones        F2, official zones, public
    user_router  -> /user/zones   F4 / FO3, the caller's personal zonings
"""

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile

from business_object.geo_zone import GeographicZone, Zoning
from business_object.user import User
from controllers.dependencies import SERVICE_ERRORS, get_current_user, http_error
from schema.zone_schema import (
    MunicipalityResponse,
    ZoneResponse,
    ZoneTypeFilter,
    ZoningCreateRequest,
    ZoningResponse,
    ZoningUpdateRequest,
)
from service.zone_service import ZoneService

router = APIRouter()
user_router = APIRouter()
service = ZoneService()


def _zone_to_response(zone: GeographicZone) -> ZoneResponse:
    return ZoneResponse(
        id=zone.id,
        name=zone.name,
        zone_type=zone.zone_type,
        insee_code=getattr(zone, "insee_code", None),
        municipalities=[
            MunicipalityResponse(insee_code=m.insee_code, name=m.name) for m in zone.get_municipalities()
        ],
    )


def _zoning_to_response(zoning: Zoning) -> ZoningResponse:
    return ZoningResponse(
        id=zoning.id,
        name=zoning.name,
        description=zoning.description,
        created_at=zoning.created_at,
        codes_insee=[m.insee_code for m in zoning.get_municipalities()],
    )


# --- F2: official zones ---

@router.get("", response_model=list[ZoneResponse])
async def list_zones(zone_type: ZoneTypeFilter = Query(default="all", alias="type")):
    """
    F2 - List the departments, the regions or both, with their municipalities.
    """
    try:
        return [_zone_to_response(zone) for zone in service.list_public_zones(zone_type)]
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


 

@user_router.get("", response_model=list[ZoningResponse])
async def list_my_zonings(user: User = Depends(get_current_user)):
    return [_zoning_to_response(z) for z in service.list_user_zonings(user)]


@user_router.post("", response_model=ZoningResponse, status_code=201)
async def create_zoning(request: ZoningCreateRequest, user: User = Depends(get_current_user)):
    """
    F4 - Create a zoning from a description and a list of INSEE codes (400 if one is unknown).
    """
    try:
        return _zoning_to_response(service.create_zoning(user, request.description, request.codes_insee))
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


@user_router.post("/import", response_model=ZoningResponse, status_code=201)
async def import_zoning(
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    user: User = Depends(get_current_user),
):
    """
    FO3 - Create a zoning from a CSV or JSON file listing INSEE codes.
    """
    try:
        content = await file.read()
        return _zoning_to_response(service.import_zoning(user, file.filename or "", content, description))
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


@user_router.patch("/{zoning_id}", response_model=ZoningResponse)
async def update_zoning(zoning_id: int, request: ZoningUpdateRequest, user: User = Depends(get_current_user)):
    """
    F4 - Change the description and/or add or remove municipalities (owner only).
    """
    try:
        zoning = service.update_zoning(
            user, zoning_id, request.description, request.add_codes_insee, request.remove_codes_insee
        )
        return _zoning_to_response(zoning)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


@user_router.delete("/{zoning_id}", status_code=204)
async def delete_zoning(zoning_id: int, user: User = Depends(get_current_user)):
    """
    F4 - Delete a zoning (owner only).
    """
    try:
        service.delete_zoning(user, zoning_id)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return Response(status_code=204)