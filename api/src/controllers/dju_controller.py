"""Routes de calcul des DJU (F1, F3)."""

import csv
import io

from fastapi import APIRouter, Depends, Query, Response

from business_object.dju import DjuCalculation
from business_object.geo_zone import GeographicZone
from business_object.user import User
from controllers.dependencies import SERVICE_ERRORS, get_optional_user, http_error
from schema.dju_schema import (
    DjuPointRequest,
    DjuResponse,
    DjuResultItem,
    DjuZoneRequest,
    DjuZoneResponse,
    DjuZoneResult,
    OutputFormat,
    StationItem,
)
from service.dju_service import DjuService
from service.temperature_service import MAX_DISTANCE_KM

router = APIRouter()
service = DjuService()

CSV_COLUMNS = ["zone", "zone_code", "mode", "period_start", "period_end", "value", "days_with_data", "observed_ratio"]


def to_items(calculation: DjuCalculation) -> list[DjuResultItem]:
    """Convertit les résultats d'un calcul en schémas."""
    return [
        DjuResultItem(
            period_start=r.period_start,
            period_end=r.period_end,
            value=r.value,
            days_with_data=r.days_with_data,
            observed_ratio=r.observed_ratio,
        )
        for r in calculation.results
    ]


def zone_code(zone: GeographicZone) -> str | None:
    """Code de la zone pour l'utilisateur : code INSEE, ou identifiant pour un zonage personnel."""
    insee_code = getattr(zone, "insee_code", None)
    if insee_code is not None:
        return insee_code
    return None if zone.id is None else str(zone.id)


def to_stations(calculation: DjuCalculation) -> list[StationItem]:
    """Stations utilisées pour un point, de la plus proche à la plus éloignée."""
    return [
        StationItem(
            station_code=s.station_code,
            name=s.name,
            latitude=s.latitude,
            longitude=s.longitude,
            altitude=s.altitude,
            distance_km=round(s.distance_to(calculation.latitude, calculation.longitude), 1),
        )
        for s in calculation.candidate_stations
    ]


def to_csv(rows: list[tuple[str, str | None, DjuCalculation]]) -> Response:
    """Construit la réponse CSV à partir de triplets (nom de zone, code de zone, calcul)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for zone_name, code, calc in rows:
        for r in calc.results:
            writer.writerow(
                [zone_name, code or "", calc.type.mode, r.period_start, r.period_end,
                 r.value, r.days_with_data, r.observed_ratio]
            )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dju.csv"},
    )


def period_warning(request, calculation: DjuCalculation | None) -> str | None:
    """Message si la période calculée est plus courte que la période demandée, sinon None."""
    if calculation is None:
        return None
    if (calculation.start_date, calculation.end_date) == (request.start_date, request.end_date):
        return None
    return (
        f"Période raccourcie aux données disponibles : calcul du {calculation.start_date} "
        f"au {calculation.end_date} au lieu du {request.start_date} au {request.end_date}."
    )


def stations_warning(request, calculation: DjuCalculation | None) -> str | None:
    """Message si moins de stations que demandé sont assez proches du point, sinon None."""
    if calculation is None:
        return None
    found = len(calculation.candidate_stations)
    if found >= request.number_of_stations:
        return None
    return (
        f"Seulement {found} station(s) avec des relevés à moins de {MAX_DISTANCE_KM:g} km "
        f"du point, au lieu des {request.number_of_stations} demandées."
    )


def join_warnings(*warnings: str | None) -> str | None:
    """Réunit les messages non vides en un seul, ou None s'il n'y en a aucun."""
    return " ".join(w for w in warnings if w) or None


def to_zone_response(calculations: list[DjuCalculation], warning: str | None = None) -> DjuZoneResponse:
    """Regroupe les calculs par sous-zone."""
    zones: dict[tuple, DjuZoneResult] = {}
    for calc in calculations:
        key = (calc.zone.zone_type, calc.zone.id)
        if key not in zones:
            zones[key] = DjuZoneResult(
                zone_type=calc.zone.zone_type,
                zone_code=zone_code(calc.zone),
                name=calc.zone.name,
                results={},
            )
        zones[key].results[calc.type.mode] = to_items(calc)
    return DjuZoneResponse(zones=list(zones.values()), warning=warning)


@router.get("/")
def get_dju_info():
    """Vérifie que les routes DJU répondent."""
    return {"message": "Routes DJU disponibles"}


@router.post("/point", response_model=DjuResponse)
def calculate_point_dju(
    request: DjuPointRequest,
    output_format: OutputFormat = Query(default="json", alias="format"),
):
    """F1 : DJU en un point géographique."""
    try:
        calculations = service.calculate_point_dju(request)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    if output_format == "csv":
        return to_csv([("point", None, calc) for calc in calculations.values()])
    first = next(iter(calculations.values()), None)
    return DjuResponse(
        results={mode: to_items(calc) for mode, calc in calculations.items()},
        stations=to_stations(first) if first is not None else [],
        warning=join_warnings(period_warning(request, first), stations_warning(request, first)),
    )


@router.post("/zone", response_model=DjuZoneResponse)
def calculate_zone_dju(
    request: DjuZoneRequest,
    output_format: OutputFormat = Query(default="json", alias="format"),
    user: User | None = Depends(get_optional_user),
):
    """F3 : DJU sur un département, une région ou un zonage personnel."""
    try:
        calculations = service.calculate_zone_dju(request, user)
    except SERVICE_ERRORS as exc:
        raise http_error(exc) from exc
    if output_format == "csv":
        return to_csv([(calc.zone.name, zone_code(calc.zone), calc) for calc in calculations])
    return to_zone_response(
        calculations, period_warning(request, calculations[0] if calculations else None)
    )
