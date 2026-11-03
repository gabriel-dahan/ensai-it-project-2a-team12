"""Calcul des DJU sur un point GPS (F1) ou sur un territoire (F3)."""

from business_object.dju import DjuCalculation, DjuType
from business_object.user import User
from dao.dju_dao import DjuDao
from schema.dju_schema import DjuPointRequest, DjuZoneRequest
from service.errors import ServiceError
from service.temperature_service import TemperatureService
from service.zone_service import ZoneService


class DjuService:
    """Crée les calculs DJU et utilise le cache des calculs pour les territoires."""

    def __init__(self, temperature_service=None, zone_service=None, dju_dao=None):
        self.temperature_service = temperature_service or TemperatureService()
        self.zone_service = zone_service or ZoneService()
        self.dju_dao = dju_dao or DjuDao()

    @staticmethod
    def _check_request(request) -> dict[str, float]:
        """Renvoie les seuils indexés par mode ; 400 si aucun seuil ou dates incohérentes."""
        thresholds = {}
        if request.heating_threshold is not None:
            thresholds["heating"] = request.heating_threshold
        if request.cooling_threshold is not None:
            thresholds["cooling"] = request.cooling_threshold
        if not thresholds:
            raise ServiceError("Il faut au moins un seuil de chauffage ou de climatisation.", 400)
        if request.start_date > request.end_date:
            raise ServiceError("La date de début doit précéder la date de fin.", 400)
        return thresholds

    def calculate_point_dju(self, request: DjuPointRequest) -> dict[str, DjuCalculation]:
        """Un calcul par seuil pour un point GPS, sans stockage."""
        thresholds = self._check_request(request)
        stations = self.temperature_service.find_candidate_stations(
            request.latitude,
            request.longitude,
            request.number_of_stations,
            request.start_date,
            request.end_date,
        )
        if not stations:
            raise ServiceError("Aucune station météo n'a de relevés près de ce point sur la période.", 404)

        # Les températures ne dépendent pas du seuil : on les estime une seule fois
        temperatures = self.temperature_service.estimate_daily_temperatures(
            request.latitude,
            request.longitude,
            request.altitude,
            stations,
            request.start_date,
            request.end_date,
        )

        calculations = {}
        for mode, threshold in thresholds.items():
            calculation = DjuCalculation(
                id=None,
                start_date=request.start_date,
                end_date=request.end_date,
                time_step=request.time_step,
                type=DjuType(id=None, name=mode, base_temperature=threshold, mode=mode),
                latitude=request.latitude,
                longitude=request.longitude,
                altitude=request.altitude,
                number_of_stations=request.number_of_stations,
                use_altitude=request.altitude is not None,
                candidate_stations=stations,
            )
            calculation.run(temperatures)
            calculations[mode] = calculation
        return calculations

    def calculate_zone_dju(self, request: DjuZoneRequest, user: User | None) -> list[DjuCalculation]:
        """Un calcul par sous-zone et par seuil, relu du cache ou calculé puis enregistré."""
        thresholds = self._check_request(request)
        zone = self.zone_service.get_zone(request.zone_type, request.zone_id, user)

        calculations = []
        for sub_zone in self.zone_service.get_sub_zones(zone, request.aggregation_level):
            temperatures = None  # calculées au premier besoin, une fois par sous-zone
            for mode, threshold in thresholds.items():
                type_id = self.dju_dao.get_or_create_dju_type(mode, threshold)
                calculation = DjuCalculation(
                    id=None,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    time_step=request.time_step,
                    type=DjuType(id=type_id, name=mode, base_temperature=threshold, mode=mode),
                    zone=sub_zone,
                    number_of_stations=request.number_of_stations,
                    use_altitude=request.use_altitude,
                )
                calculation_id = self.dju_dao.find_calculation(
                    sub_zone.zone_type,
                    sub_zone.id,
                    type_id,
                    request.start_date,
                    request.end_date,
                    request.time_step,
                    request.number_of_stations,
                    request.use_altitude,
                )
                if calculation_id is not None:
                    calculation.id = calculation_id
                    calculation.results = self.dju_dao.get_calculation_results(calculation_id)
                else:
                    if temperatures is None:
                        temperatures = self._zone_temperatures(sub_zone, request)
                    calculation.run_for_zone(temperatures)
                    if calculation.results:
                        self.dju_dao.save_calculation(calculation)
                calculations.append(calculation)
        return calculations

    def _zone_temperatures(self, zone, request) -> dict:
        """Températures de chaque commune de la zone, indexées par code INSEE."""
        return {
            municipality.insee_code: self.temperature_service.get_municipality_temperatures(
                municipality,
                request.start_date,
                request.end_date,
                request.number_of_stations,
                request.use_altitude,
            )
            for municipality in zone.get_municipalities()
        }
