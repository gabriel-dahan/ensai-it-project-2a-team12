"""
API routes for zones creation and management.
"""

from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def get_created_zones():
    ...

@router.post("/create")
async def create_personalized_zoning():
    ...

"""
Controller for:
  F2 — read-only access to administrative zonings (Region, Department).
  F4 — an authenticated user's own custom Zoning (set of municipalities).
"""

from __future__ import annotations

from business_object.geo_zone import GeographicZone, Zoning
from business_object.user import User
from dao.geo_zone_dao import GeoZoneDao
from controllers.base_controller import BaseController


class ZoneController(BaseController):
    

    def __init__(self) -> None:
        super().__init__()
        self.dao = GeoZoneDao()

    # --- F2: référentiel administratif ---

    def list_regions(self):
        return self.dao.list_regions()

    def list_departments(self):
        return self.dao.list_departments()

    def get_municipalities_of_zone(self, zone_type: str, zone_id: int) -> list:
        """Résout la liste des communes d'un territoire, sans reconstruire
        un objet Region/Department complet — le DAO réel n'expose que des
        requêtes par id de département pour l'instant."""
        if zone_type == "department":
            return self.dao.get_municipalities_by_department(zone_id)
        if zone_type == "region":
            return self.dao.get_municipalities_by_region(zone_id)
        if zone_type == "zoning":
            zoning = self.dao.get_zoning(zone_id)
            if zoning is None:
                raise ValueError(f"No zoning with id {zone_id}")
            return zoning.get_municipalities()
        raise ValueError(f"Unknown zone_type: {zone_type!r}")

    def build_zone(self, zone_type: str, zone_id: int) -> GeographicZone:
        """Construit un GeographicZone porteur des communes résolues, pour
        que DjuCalculation.run() puisse appeler zone.get_municipalities()
        de façon uniforme quel que soit le type de territoire demandé."""
        municipalities = self.get_municipalities_of_zone(zone_type, zone_id)
        return Zoning(id=None, name=f"{zone_type}:{zone_id}", municipalities=municipalities)

    # --- F4: zonages personnalisés d'un utilisateur authentifié ---
    # Identifiés par code INSEE plutôt que par id numérique : c'est la clé
    # naturelle exposée par get_municipality_by_insee(), et c'est aussi ce
    # que l'utilisateur/le fichier CSV (FO3) fournira le plus naturellement.

    def create_zoning(self, user: User, description: str, insee_codes: list[str]) -> Zoning:
        zoning = user.create_zoning(description)
        for code in insee_codes:
            municipality = self.dao.get_municipality_by_insee(code)
            if municipality is None:
                raise ValueError(f"No municipality with INSEE code {code!r}")
            zoning.add_municipality(municipality)
        return self.dao.save_zoning(zoning)

    def add_municipality(self, zoning: Zoning, insee_code: str) -> Zoning:
        municipality = self.dao.get_municipality_by_insee(insee_code)
        if municipality is None:
            raise ValueError(f"No municipality with INSEE code {insee_code!r}")
        zoning.add_municipality(municipality)
        return self.dao.save_zoning(zoning)

    def remove_municipality(self, zoning: Zoning, insee_code: str) -> Zoning:
        municipality = self.dao.get_municipality_by_insee(insee_code)
        if municipality is not None:
            zoning.remove_municipality(municipality)
        return self.dao.save_zoning(zoning)

    def list_user_zonings(self, user: User) -> list[Zoning]:
        return self.dao.list_zonings_by_user(user.id)

    def delete_zoning(self, zoning: Zoning) -> None:
        self.dao.delete_zoning(zoning.id)