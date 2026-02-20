"""Number entities for Arctic Spa."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ArcticSpaEntity
from .spa_client import ArcticSpaClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arctic Spa number entities."""
    client: ArcticSpaClient = entry.runtime_data
    config = client.config or {}
    entities: list[NumberEntity] = []

    if config.get("onzen", False):
        entities.append(ArcticSpaOnzenDuration(client))

    if entities:
        async_add_entities(entities)


class ArcticSpaOnzenDuration(ArcticSpaEntity, NumberEntity):
    """Number entity for Onzen salt cell run duration (hours per day)."""

    _attr_translation_key = "onzen_duration"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 1
    _attr_native_max_value = 24
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, client: ArcticSpaClient) -> None:
        super().__init__(client, "onzen_duration")

    @property
    def native_value(self) -> float | None:
        """Return the current Onzen duration in hours."""
        if not self._client.onzen_settings:
            return None
        return self._client.onzen_settings.get("duration_hours")

    async def async_set_native_value(self, value: float) -> None:
        """Set the Onzen duration in hours."""
        await self._client.set_onzen_duration(value)
