"""
Business logic for DJU calculations.
"""

from typing import NoReturn

from business_object.user import User
from schema.dju_schema import DjuPointRequest, DjuZoneRequest
from service.errors import NotImplementedFeature


class DjuService:
    """
    Service responsible for DJU calculations.
    """

    @staticmethod
    def calculate_heating_dju(
        average_temperature: float,
        heating_threshold: float,
    ) -> float:
        """
        Calculate heating DJU for one day.
        """
        return max(
            heating_threshold - average_temperature,
            0,
        )

    @staticmethod
    def calculate_cooling_dju(
        average_temperature: float,
        cooling_threshold: float,
    ) -> float:
        """
        Calculate cooling DJU for one day.
        """
        return max(
            average_temperature - cooling_threshold,
            0,
        )

    def calculate_point_dju(
        self,
        request: DjuPointRequest,
        user: User | None,
    ) -> NoReturn:
        """DJU for one geographic point. Not available until temperature estimation exists."""
        raise NotImplementedFeature("Point DJU calculation is not implemented yet.")

    def calculate_zone_dju(
        self,
        request: DjuZoneRequest,
        user: User | None,
    ) -> NoReturn:
        """DJU for a department, region or personal zoning. Not available yet."""
        raise NotImplementedFeature("Zone DJU calculation is not implemented yet.")