"""Zones officielles et zonages personnalisés."""

import csv
import io
import json
import os

from business_object.geo_zone import GeographicZone, Municipality, Zoning
from business_object.user import User
from dao.dju_dao import DjuDao
from dao.geo_zone_dao import GeoZoneDao
from dao.zoning_dao import ZoningDao
from service.errors import ServiceError


class ZoneService:
    """Lecture des territoires et gestion des zonages des utilisateurs."""

    def __init__(self, zone_dao=None, zoning_dao=None, dju_dao=None):
        self.zone_dao = zone_dao or GeoZoneDao()
        self.zoning_dao = zoning_dao or ZoningDao()
        self.dju_dao = dju_dao or DjuDao()

    def list_public_zones(self, zone_type: str) -> list[GeographicZone]:
        """Régions, départements, ou les deux (sans leurs communes)."""
        if zone_type == "region":
            return self.zone_dao.get_regions()
        if zone_type == "department":
            return self.zone_dao.get_departments()
        if zone_type == "all":
            return self.zone_dao.get_regions() + self.zone_dao.get_departments()
        raise ServiceError(f"Type de zone inconnu : {zone_type}.", 400)

    def list_user_zonings(self, user: User) -> list[Zoning]:
        """Zonages de l'utilisateur."""
        return self.zoning_dao.find_by_user(user.id)

    def get_zone(self, zone_type: str, zone_id: int, user: User | None = None) -> GeographicZone:
        """Zone avec ses communes ; 404 si absente, 401/403 pour un zonage."""
        if zone_type == "region":
            zone = self.zone_dao.get_region_by_id(zone_id, with_municipalities=True)
        elif zone_type == "department":
            zone = self.zone_dao.get_department_by_id(zone_id, with_municipalities=True)
        elif zone_type == "zoning":
            return self._get_owned_zoning(user, zone_id)
        else:
            raise ServiceError(f"Type de zone inconnu : {zone_type}.", 400)
        if zone is None:
            raise ServiceError("Zone introuvable.", 404)
        return zone

    def get_sub_zones(self, zone: GeographicZone, aggregation_level: str) -> list[GeographicZone]:
        """Découpe la zone selon le niveau d'agrégation demandé."""
        if aggregation_level == "zone":
            return [zone]
        if aggregation_level == "municipality":
            return zone.get_municipalities()
        if aggregation_level == "department":
            if zone.zone_type == "region":
                return zone.departments
            if zone.zone_type == "department":
                return [zone]
            raise ServiceError("Un zonage personnalisé ne peut pas être découpé par département.", 400)
        raise ServiceError(f"Niveau d'agrégation inconnu : {aggregation_level}.", 400)

    def create_zoning(self, user: User, name: str, description: str | None, codes_insee: list[str]) -> Zoning:
        """Crée un zonage à partir de codes INSEE ; 400 si un code est inconnu."""
        codes = self._clean_codes(codes_insee)
        if not codes:
            raise ServiceError("Aucun code INSEE fourni.", 400)
        zoning = user.create_zoning(name=name, description=description)
        for municipality in self._find_municipalities(codes):
            zoning.add_municipality(municipality)
        return self.zoning_dao.create(zoning)

    def import_zoning(
        self, user: User, filename: str, content: str, description: str | None = None, name: str | None = None
    ) -> Zoning:
        """Crée un zonage à partir du texte d'un fichier CSV ou JSON."""
        base_name, extension = os.path.splitext(os.path.basename(filename))
        extension = extension.lower()
        if extension == ".csv":
            codes = self._read_csv_codes(content)
        elif extension == ".json":
            codes = self._read_json_codes(content)
        else:
            raise ServiceError("Format de fichier non pris en charge : .csv ou .json attendu.", 400)
        if not self._clean_codes(codes):
            raise ServiceError("Le fichier ne contient aucun code INSEE.", 400)
        return self.create_zoning(user, name or base_name, description, codes)

    def update_zoning(
        self,
        user: User,
        zoning_id: int,
        description: str | None,
        add_codes_insee: list[str],
        remove_codes_insee: list[str],
    ) -> Zoning:
        """Modifie un zonage puis supprime ses calculs stockés, devenus faux."""
        zoning = self._get_owned_zoning(user, zoning_id)
        if description is not None:
            zoning.description = description

        codes_to_add = self._clean_codes(add_codes_insee)
        if codes_to_add:
            for municipality in self._find_municipalities(codes_to_add):
                zoning.add_municipality(municipality)

        codes_to_remove = set(self._clean_codes(remove_codes_insee))
        for municipality in list(zoning.municipalities):
            if municipality.insee_code in codes_to_remove:
                zoning.remove_municipality(municipality)

        if not zoning.municipalities:
            raise ServiceError("Un zonage doit contenir au moins une commune.", 400)

        self.zoning_dao.update(zoning)
        self.dju_dao.delete_calculations_for_zone("zoning", zoning.id)
        return zoning

    def delete_zoning(self, user: User, zoning_id: int) -> None:
        """Supprime les calculs stockés du zonage, puis le zonage."""
        zoning = self._get_owned_zoning(user, zoning_id)
        self.dju_dao.delete_calculations_for_zone("zoning", zoning.id)
        self.zoning_dao.delete(zoning.id)

    def _get_owned_zoning(self, user: User | None, zoning_id: int) -> Zoning:
        """Zonage de l'utilisateur ; 401 sans utilisateur, 404 si absent, 403 s'il appartient à un autre."""
        if user is None:
            raise ServiceError("Connexion requise pour accéder à un zonage personnalisé.", 401)
        zoning = self.zoning_dao.find_by_id(zoning_id)
        if zoning is None:
            raise ServiceError("Zonage introuvable.", 404)
        if not zoning.is_owned_by(user):
            raise ServiceError("Ce zonage appartient à un autre utilisateur.", 403)
        return zoning

    def _find_municipalities(self, codes: list[str]) -> list[Municipality]:
        """Communes des codes INSEE ; 400 avec la liste des codes inconnus."""
        municipalities = self.zone_dao.get_municipalities_by_insee(codes)
        found = {municipality.insee_code for municipality in municipalities}
        unknown = [code for code in codes if code not in found]
        if unknown:
            raise ServiceError("Codes INSEE inconnus : " + ", ".join(unknown) + ".", 400)
        return municipalities

    @staticmethod
    def _clean_codes(codes) -> list[str]:
        """Codes sans espaces, sans valeurs vides et sans doublons (ordre conservé)."""
        cleaned = [str(code).strip() for code in codes or []]
        return list(dict.fromkeys(code for code in cleaned if code))

    @staticmethod
    def _read_csv_codes(content: str) -> list[str]:
        """Codes INSEE d'un CSV : colonne code_insee si présente, sinon première colonne."""
        content = content.lstrip("﻿")
        first_line = content.split("\n", 1)[0]
        delimiter = ";" if ";" in first_line else ","
        try:
            rows = [row for row in csv.reader(io.StringIO(content), delimiter=delimiter) if row]
        except csv.Error:
            raise ServiceError("Fichier CSV illisible.", 400) from None
        if not rows:
            return []

        header = [cell.strip().lower() for cell in rows[0]]
        column = 0
        if "code_insee" in header:
            column = header.index("code_insee")
            rows = rows[1:]
        elif not rows[0][0].strip()[:1].isdigit():
            rows = rows[1:]  # en-tête : un code INSEE commence toujours par un chiffre
        return [row[column] for row in rows if len(row) > column]

    @staticmethod
    def _read_json_codes(content: str) -> list[str]:
        """Codes INSEE d'un JSON : liste de chaînes ou objet {"codes_insee": [...]}."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ServiceError("Fichier JSON illisible.", 400) from None
        if isinstance(data, dict):
            data = data.get("codes_insee")
        if not isinstance(data, list):
            raise ServiceError("Le fichier JSON doit contenir une liste de codes INSEE.", 400)
        return [str(code) for code in data]
