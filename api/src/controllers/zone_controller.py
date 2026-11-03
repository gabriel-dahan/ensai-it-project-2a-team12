"""Routes des zones : /zones (F2, public) et /user/zones (F4, FO3, zonages personnels)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from business_object.geo_zone import GeographicZone, Zoning
from business_object.user import User
from controllers.dependencies import SERVICE_ERRORS, get_current_user, http_error
from schema.zone_schema import (
    MunicipalityResponse,
    ZoneDetailResponse,
    ZoneResponse,
    ZoneTypeFilter,
    ZoningCreateRequest,
    ZoningImportRequest,
    ZoningResponse,
    ZoningUpdateRequest,
)
from service.zone_service import ZoneService

router = APIRouter()
user_router = APIRouter()
service = ZoneService()


def to_zone_response(zone: GeographicZone) -> ZoneResponse:
    """Convertit une zone officielle en schéma léger."""
    return ZoneResponse(
        id=zone.id, name=zone.name, zone_type=zone.zone_type, insee_code=zone.insee_code
    )


def to_zone_detail(zone: GeographicZone) -> ZoneDetailResponse:
    """Convertit une zone officielle en schéma avec ses communes."""
    return ZoneDetailResponse(
        id=zone.id,
        name=zone.name,
        zone_type=zone.zone_type,
        insee_code=zone.insee_code,
        municipalities=[
            MunicipalityResponse(insee_code=m.insee_code, name=m.name)
            for m in zone.get_municipalities()
        ],
    )


def to_zoning_response(zoning: Zoning) -> ZoningResponse:
    """Convertit un zonage personnel en schéma."""
    return ZoningResponse(
        id=zoning.id,
        name=zoning.name,
        description=zoning.description,
        created_at=zoning.created_at,
        codes_insee=[m.insee_code for m in zoning.get_municipalities()],
    )


# F2 : zones officielles


@router.get("", response_model=list[ZoneResponse])
def list_zones(zone_type: ZoneTypeFilter = Query(default="all", alias="type")):
    """F2 : liste des régions et/ou des départements, sans les communes."""
    try:
        return [to_zone_response(zone) for zone in service.list_public_zones(zone_type)]
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


@router.get("/{zone_type}/{zone_id}", response_model=ZoneDetailResponse)
def get_zone(zone_type: Literal["region", "department"], zone_id: int):
    """F2 : détail d'une région ou d'un département avec ses communes."""
    try:
        return to_zone_detail(service.get_zone(zone_type, zone_id))
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


# F4 et FO3 : zonages de l'utilisateur connecté


@user_router.get("", response_model=list[ZoningResponse])
def list_my_zonings(user: User = Depends(get_current_user)):
    """Liste les zonages de l'utilisateur."""
    try:
        return [to_zoning_response(z) for z in service.list_user_zonings(user)]
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc


@user_router.post("", response_model=ZoningResponse, status_code=201)
def create_zoning(request: ZoningCreateRequest, user: User = Depends(get_current_user)):
    """F4 : crée un zonage à partir d'une liste de codes INSEE."""
    try:
        zoning = service.create_zoning(user, request.name, request.description, request.codes_insee)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return to_zoning_response(zoning)


@user_router.post("/import", response_model=ZoningResponse, status_code=201)
def import_zoning(request: ZoningImportRequest, user: User = Depends(get_current_user)):
    """FO3 : crée un zonage à partir du contenu d'un fichier CSV ou JSON."""
    try:
        zoning = service.import_zoning(
            user, request.filename, request.content, request.description, request.name
        )
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return to_zoning_response(zoning)


@user_router.patch("/{zoning_id}", response_model=ZoningResponse)
def update_zoning(
    zoning_id: int, request: ZoningUpdateRequest, user: User = Depends(get_current_user)
):
    """F4 : modifie la description et/ou les communes d'un zonage."""
    try:
        zoning = service.update_zoning(
            user, zoning_id, request.description, request.add_codes_insee, request.remove_codes_insee
        )
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return to_zoning_response(zoning)


@user_router.delete("/{zoning_id}", status_code=204)
def delete_zoning(zoning_id: int, user: User = Depends(get_current_user)):
    """F4 : supprime un zonage."""
    try:
        service.delete_zoning(user, zoning_id)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    return Response(status_code=204)
