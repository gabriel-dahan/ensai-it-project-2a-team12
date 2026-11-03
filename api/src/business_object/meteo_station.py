"""Station météo de Météo-France."""

from dataclasses import dataclass

from .geo_zone import haversine_km


@dataclass
class MeteoStation:
    id: int | None
    station_code: str
    name: str | None
    latitude: float
    longitude: float
    altitude: float | None = None

    def distance_to(self, lat: float, lon: float) -> float:
        """Distance en km jusqu'au point donné."""
        return haversine_km(self.latitude, self.longitude, lat, lon)
