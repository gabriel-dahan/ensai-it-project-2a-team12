"""Zones géographiques : régions, départements, communes et zonages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from math import asin, cos, radians, sin, sqrt
from typing import ClassVar

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en km entre deux points GPS (formule de Haversine)."""
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    d_lat = rlat2 - rlat1
    d_lon = rlon2 - rlon1
    a = sin(d_lat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


@dataclass
class GeographicZone(ABC):
    """Zone abstraite sur laquelle on peut calculer des DJU."""

    id: int | None
    name: str
    zone_type: ClassVar[str] = "zone"

    @abstractmethod
    def get_municipalities(self) -> list["Municipality"]:
        """Communes couvertes par la zone."""


@dataclass
class Region(GeographicZone):
    insee_code: str
    departments: list["Department"] = field(default_factory=list)
    zone_type = "region"

    def get_municipalities(self) -> list["Municipality"]:
        return [m for dept in self.departments for m in dept.get_municipalities()]

    def add_department(self, department: "Department") -> None:
        department.region_id = self.id
        self.departments.append(department)


@dataclass
class Department(GeographicZone):
    insee_code: str
    region_id: int | None = None
    municipalities: list["Municipality"] = field(default_factory=list)
    zone_type = "department"

    def get_municipalities(self) -> list["Municipality"]:
        return list(self.municipalities)

    def add_municipality(self, municipality: "Municipality") -> None:
        municipality.department_id = self.id
        self.municipalities.append(municipality)


@dataclass
class Municipality(GeographicZone):
    insee_code: str
    latitude: float
    longitude: float
    altitude: float | None = None
    population: int | None = None
    department_id: int | None = None
    zone_type = "municipality"

    def get_municipalities(self) -> list["Municipality"]:
        return [self]

    def distance_to(self, lat: float, lon: float) -> float:
        """Distance en km jusqu'au point donné."""
        return haversine_km(self.latitude, self.longitude, lat, lon)


@dataclass
class Zoning(GeographicZone):
    """Zonage personnalisé : un ensemble de communes choisi par un utilisateur."""

    description: str | None = None
    created_at: date = field(default_factory=date.today)
    owner_id: int | None = None
    municipalities: list[Municipality] = field(default_factory=list)
    zone_type = "zoning"

    def add_municipality(self, m: Municipality) -> None:
        """Ajoute une commune si son code INSEE n'est pas déjà présent."""
        if not any(existing.insee_code == m.insee_code for existing in self.municipalities):
            self.municipalities.append(m)

    def remove_municipality(self, m: Municipality) -> None:
        """Retire la commune de même code INSEE."""
        self.municipalities = [
            existing for existing in self.municipalities if existing.insee_code != m.insee_code
        ]

    def get_municipalities(self) -> list[Municipality]:
        return list(self.municipalities)

    def is_owned_by(self, user) -> bool:
        """Vrai si l'utilisateur est le propriétaire du zonage."""
        return user is not None and user.id == self.owner_id
