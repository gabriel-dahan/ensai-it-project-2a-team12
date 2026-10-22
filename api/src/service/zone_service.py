"""Official zones and personal zonings."""

from typing import NoReturn

from business_object.user import User
from service.errors import NotImplementedFeature


class ZoneService:
    """Zone catalogue and personal zonings. The behaviour is not implemented yet."""

    def list_public_zones(self, zone_type: str) -> NoReturn:
        """List departments, regions, or both."""
        raise NotImplementedFeature("Listing official zones is not implemented yet.")

    def list_user_zonings(self, user: User) -> NoReturn:
        """List the zonings owned by this user."""
        raise NotImplementedFeature("Listing personal zonings is not implemented yet.")

    def create_zoning(self, user: User, description: str, codes_insee: list[str]) -> NoReturn:
        """Create a zoning from a description and INSEE codes."""
        raise NotImplementedFeature("Creating a zoning is not implemented yet.")

    def import_zoning(
        self,
        user: User,
        filename: str,
        content: bytes,
        description: str | None,
    ) -> NoReturn:
        """Create a zoning from an uploaded CSV or JSON file."""
        raise NotImplementedFeature("Importing a zoning is not implemented yet.")

    def update_zoning(
        self,
        user: User,
        zoning_id: int,
        description: str | None,
        add_codes_insee: list[str],
        remove_codes_insee: list[str],
    ) -> NoReturn:
        """Update a zoning owned by this user."""
        raise NotImplementedFeature("Updating a zoning is not implemented yet.")

    def delete_zoning(self, user: User, zoning_id: int) -> NoReturn:
        """Delete a zoning owned by this user."""
        raise NotImplementedFeature("Deleting a zoning is not implemented yet.")
