"""Light entity for Arctic Spa."""

from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ArcticSpaEntity
from .spa_client import ArcticSpaClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arctic Spa light entity."""
    client: ArcticSpaClient = entry.runtime_data
    if client.config and not client.config.get("lights"):
        return
    async_add_entities([ArcticSpaLight(client)])


class ArcticSpaLight(ArcticSpaEntity, LightEntity):
    """Light entity for the spa."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    def __init__(self, client: ArcticSpaClient) -> None:
        super().__init__(client, "light")

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        if not self._client.live:
            return None
        return self._client.live.get("lights", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the light."""
        await self._client.send_command(set_lights=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the light."""
        await self._client.send_command(set_lights=False)
