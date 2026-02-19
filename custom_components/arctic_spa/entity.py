"""Base entity for Arctic Spa integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .spa_client import ArcticSpaClient


class ArcticSpaEntity(Entity):
    """Base entity for all Arctic Spa entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, client: ArcticSpaClient, key: str) -> None:
        self._client = client
        self._attr_unique_id = f"{client.host}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.host)},
            name="Arctic Spa",
            manufacturer="Arctic Spas",
        )

    @property
    def available(self) -> bool:
        """Return True if the spa is connected."""
        return self._client.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to client updates when added to HA."""
        self.async_on_remove(
            self._client.register_callback(self.async_write_ha_state)
        )
