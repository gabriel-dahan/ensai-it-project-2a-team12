"""Routes de calcul des DJU (F1, F3)."""

import csv
import io

from fastapi import APIRouter, Depends, Query, Response

from business_object.dju import DjuCalculation
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
)
from service.dju_service import DjuService

router = APIRouter()
service = DjuService()

CSV_COLUMNS = ["zone", "mode", "period_start", "period_end", "value", "days_with_data", "observed_ratio"]


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


def to_csv(rows: list[tuple[str, DjuCalculation]]) -> Response:
    """Construit la réponse CSV à partir de couples (nom de zone, calcul)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for zone_name, calc in rows:
        for r in calc.results:
            writer.writerow(
                [zone_name, calc.type.mode, r.period_start, r.period_end,
                 r.value, r.days_with_data, r.observed_ratio]
            )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dju.csv"},
    )


def to_zone_response(calculations: list[DjuCalculation]) -> DjuZoneResponse:
    """Regroupe les calculs par sous-zone."""
    zones: dict[tuple, DjuZoneResult] = {}
    for calc in calculations:
        key = (calc.zone.zone_type, calc.zone.id)
        if key not in zones:
            zones[key] = DjuZoneResult(
                zone_type=calc.zone.zone_type, zone_id=calc.zone.id, name=calc.zone.name, results={}
            )
        zones[key].results[calc.type.mode] = to_items(calc)
    return DjuZoneResponse(zones=list(zones.values()))


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
        return to_csv([("point", calc) for calc in calculations.values()])
    return DjuResponse(results={mode: to_items(calc) for mode, calc in calculations.items()})


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
        return to_csv([(calc.zone.name, calc) for calc in calculations])
    return to_zone_response(calculations)
