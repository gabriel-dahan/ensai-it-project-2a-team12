"""Calcul des DJU sur un point GPS (F1) ou sur un territoire (F3)."""

from datetime import date

from business_object.dju import DjuCalculation, DjuType
from business_object.user import User
from dao.dju_dao import DjuDao
from schema.dju_schema import DjuPointRequest, DjuZoneRequest
from service.errors import ServiceError
from service.temperature_service import TemperatureService
from service.zone_service import ZoneService

POINT = "point"  # nom du lieu dans les tableaux de températures d'un calcul ponctuel


class DjuService:
    """Crée les calculs DJU et utilise le cache des calculs pour les territoires."""

    def __init__(self, temperature_service=None, zone_service=None, dju_dao=None):
        self.temperature_service = temperature_service or TemperatureService()
        self.zone_service = zone_service or ZoneService()
        self.dju_dao = dju_dao or DjuDao()

    def _check_request(self, request) -> tuple[dict[str, float], date, date]:
        """Renvoie les seuils indexés par mode et la période ramenée aux données disponibles.

        400 si aucun seuil, si les dates sont dans le désordre ou si la période n'a aucune donnée.
        """
        thresholds = {}
        if request.heating_threshold is not None:
            thresholds["heating"] = request.heating_threshold
        if request.cooling_threshold is not None:
            thresholds["cooling"] = request.cooling_threshold
        if not thresholds:
            raise ServiceError("Il faut au moins un seuil de chauffage ou de climatisation.", 400)
        if request.start_date > request.end_date:
            raise ServiceError("La date de début doit précéder la date de fin.", 400)

        first_date, last_date = self.temperature_service.get_data_period()
        if first_date is None:
            raise ServiceError("Aucun relevé de température n'est chargé en base.", 404)
        # La période est raccourcie aux données disponibles ; le contrôleur le signale
        start_date = max(request.start_date, first_date)
        end_date = min(request.end_date, last_date)
        if start_date > end_date:
            raise ServiceError(
                f"Aucune donnée sur cette période : les relevés vont du {first_date} au {last_date}.",
                400,
            )
        return thresholds, start_date, end_date

    def calculate_point_dju(self, request: DjuPointRequest) -> dict[str, DjuCalculation]:
        """Un calcul par seuil pour un point GPS, sans stockage."""
        thresholds, start_date, end_date = self._check_request(request)
        locations = {POINT: (request.latitude, request.longitude, request.altitude)}
        stations, reports = self.temperature_service.find_candidate_stations(
            locations, request.number_of_stations, start_date, end_date
        )
        if not stations[POINT]:
            raise ServiceError("Aucune station météo n'a de relevés près de ce point sur la période.", 404)

        # Les températures ne dépendent pas du seuil : on les estime une seule fois
        means, observed = self.temperature_service.estimate_daily_temperatures(
            locations, stations, reports
        )

        calculations = {}
        for mode, threshold in thresholds.items():
            calculation = DjuCalculation(
                id=None,
                start_date=start_date,
                end_date=end_date,
                time_step=request.time_step,
                type=DjuType(id=None, name=mode, base_temperature=threshold, mode=mode),
                latitude=request.latitude,
                longitude=request.longitude,
                altitude=request.altitude,
                number_of_stations=request.number_of_stations,
                use_altitude=request.altitude is not None,
                candidate_stations=stations[POINT],
            )
            calculation.run(means[POINT], observed[POINT])
            calculations[mode] = calculation
        return calculations

    def calculate_zone_dju(self, request: DjuZoneRequest, user: User | None) -> list[DjuCalculation]:
        """Un calcul par sous-zone et par seuil, relu du cache ou calculé puis enregistré."""
        thresholds, start_date, end_date = self._check_request(request)
        zone = self.zone_service.get_zone(request.zone_type, request.zone_id, user)

        # Un type de DJU par seuil, cherché (ou créé) une seule fois
        dju_types = {
            mode: DjuType(
                id=self.dju_dao.get_or_create_dju_type(mode, threshold),
                name=mode,
                base_temperature=threshold,
                mode=mode,
            )
            for mode, threshold in thresholds.items()
        }

        # 1. Les calculs déjà stockés sont relus, les autres sont mis de côté
        calculations, to_compute = [], []
        for sub_zone in self.zone_service.get_sub_zones(zone, request.aggregation_level):
            for dju_type in dju_types.values():
                calculation = DjuCalculation(
                    id=None,
                    start_date=start_date,
                    end_date=end_date,
                    time_step=request.time_step,
                    type=dju_type,
                    zone=sub_zone,
                    number_of_stations=request.number_of_stations,
                    use_altitude=request.use_altitude,
                )
                calculation_id = self.dju_dao.find_calculation(
                    sub_zone.zone_type,
                    sub_zone.id,
                    dju_type.id,
                    start_date,
                    end_date,
                    request.time_step,
                    request.number_of_stations,
                    request.use_altitude,
                )
                if calculation_id is not None:
                    calculation.id = calculation_id
                    calculation.results = self.dju_dao.get_calculation_results(calculation_id)
                else:
                    to_compute.append(calculation)
                calculations.append(calculation)

        # 2. Les températures de toutes les communes à calculer sont estimées en une fois
        if to_compute:
            municipalities = {
                m.insee_code: m for calculation in to_compute for m in calculation.zone.get_municipalities()
            }
            means, observed = self.temperature_service.get_municipality_temperatures(
                list(municipalities.values()),
                start_date,
                end_date,
                request.number_of_stations,
                request.use_altitude,
            )
            for calculation in to_compute:
                calculation.run_for_zone(means, observed)
                if calculation.results:
                    self.dju_dao.save_calculation(calculation)
        return calculations
