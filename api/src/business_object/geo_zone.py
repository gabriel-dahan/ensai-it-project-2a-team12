"""Zones géographiques : régions, départements, communes et zonages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar

import numpy as np

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance en km entre des points GPS (formule de Haversine).

    Accepte des nombres ou des tableaux numpy : TemperatureService s'en sert pour
    calculer en une fois la distance d'un lieu à toutes les stations.
    """
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


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
