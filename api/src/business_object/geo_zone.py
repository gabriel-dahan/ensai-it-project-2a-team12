from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import asin, cos, radians, sin, sqrt
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from .meteo_station  import MeteoStation
    from .user import User

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    d_lat = rlat2 - rlat1
    d_lon = rlon2 - rlon1
    a = sin(d_lat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(d_lon / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(a))

@dataclass
class GeographicZone:
    """ base class for a DJU calculation."""
    id: Optional[int]
    name : str
    _zone_type:ClassVar[str] = "zone"

    id; optional[str]
    name: str
     @property
    def zone_type(self) -> str:
        return self._zone_type

    def get_municipalities(self) -> list["Municipality"]:
        """Flat list of municipalities covered by this zone. Base = none."""
        return []

    def contains_point(self, lat: float, lon: float, tolerance_km: float = 5.0) -> bool:
        """Heuristic containment check.

        The referentiel only gives commune centroids, not polygon
        boundaries, so this returns True if the point lies within
        `tolerance_km` of at least one municipality's centroid in this
        zone. For an authoritative answer, resolve the point to its
        commune first and check membership directly.
        """
        return any(
            m.distance_to(lat, lon) <= tolerance_km for m in self.get_municipalities()
        )

@dataclass
class Region(GeographicZone):
     insee_code: str
    departments: list["Department"] = field(default_factory=list)
    _zone_type: ClassVar[str] = "region"
 
    def add_department(self, department: "Department") -> None:
        department.region = self
        self.departments.append(department)
    def get_municipalities(self) -> list["Municipality"]:
        return [m for dept in self.departments for m in dept.get_municipalities()]
    def add_department(self, department: "Department") -> None:
        department.region = self
        self.departments.append(department)
    

@dataclass
class Department(GeographicZone):
    insee_code: str
    region: Optional[Region] = None
    municipalities: list["Municipality"] = field(default_factory=list)

    _zone_type: ClassVar[str] = "department"

    def get_municipalities(self) -> list["Municipality"]:
        return list(self.municipalities)

    def add_municipality(self, municipality: "Municipality") -> None:
        municipality.department = self
        self.municipalities.append(municipality)


@dataclass
class Municipality(GeographicZone):
    insee_code: str
    latitude: float
    longitude: float
    altitude: float
    population: int
    department: Optional[Department] = None
    # Stations already associated to this municipality (e.g. loaded by the
    # DAO layer). get_nearby_stations() ranks and slices this list — it
    # does not query a repository itself, per the "business_object" /
    # "dao" split visible in your project structure.
    stations: list["MeteoStation"] = field(default_factory=list)

    _zone_type: ClassVar[str] = "municipality"

    def get_municipalities(self) -> list["Municipality"]:
        return [self]

    def distance_to(self, lat: float, lon: float) -> float:
        """Great-circle distance in km to a given point (haversine)."""
        return _haversine_km(self.latitude, self.longitude, lat, lon)

    def get_nearby_stations(self, n: int) -> list["MeteoStation"]:
        ranked = sorted(
            self.stations, key=lambda s: s.distance_to(self.latitude, self.longitude)
        )
        return ranked[:n]


@dataclass
class Zoning(GeographicZone):
    """User-defined zone made of an arbitrary set of municipalities."""

    created_at: date = field(default_factory=lambda: datetime.utcnow().date())
    description: Optional[str] = None
    owner: Optional["User"] = None  # implied by the User "1" --> "*" Zoning link
    municipalities: list[Municipality] = field(default_factory=list)

    _zone_type: ClassVar[str] = "zoning"

    def add_municipality(self, m: Municipality) -> None:
        if not any(existing.id == m.id for existing in self.municipalities):
            self.municipalities.append(m)

    def remove_municipality(self, m: Municipality) -> None:
        self.municipalities = [existing for existing in self.municipalities if existing.id != m.id]

    def get_municipalities(self) -> list["Municipality"]:
        return list(self.municipalities)
    
    


    


    