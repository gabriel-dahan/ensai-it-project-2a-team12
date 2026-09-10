"""
Business logic for DJU calculations.
"""


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