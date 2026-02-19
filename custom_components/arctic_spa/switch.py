"""Switch entities for Arctic Spa."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ArcticSpaEntity
from .spa_client import ArcticSpaClient


@dataclass
class SwitchConfig:
    """Configuration for a spa switch entity."""

    key: str
    live_key: str
    command_key: str
    translation_key: str
    icon: str
    config_key: str | None = None  # Key in config to check if installed


SWITCHES: list[SwitchConfig] = [
    SwitchConfig("stereo", "stereo", "set_stereo", "stereo", "mdi:speaker", "stereo"),
    SwitchConfig("onzen", "onzen", "set_onzen", "onzen", "mdi:water-check", "onzen"),
    SwitchConfig("ozone", "ozone", "set_ozone", "ozone", "mdi:molecule", None),
    SwitchConfig("exhaust_fan", "exhaust_fan", "set_exhaust_fan", "exhaust_fan", "mdi:fan", "exhaust_fan"),
    SwitchConfig("filter", "filter", "set_filter", "filter", "mdi:air-filter", "filter"),
    SwitchConfig("fogger", "fogger", "set_fogger", "fogger", "mdi:weather-fog", "fogger"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arctic Spa switch entities."""
    client: ArcticSpaClient = entry.runtime_data
    config = client.config or {}
    entities: list[SwitchEntity] = []

    for sw in SWITCHES:
        # Skip if config says this feature is not installed
        if sw.config_key and not config.get(sw.config_key, False):
            # For ozone, check ozone_peak_1
            if sw.key == "ozone" and not config.get("ozone_peak_1", False):
                continue
            elif sw.config_key:
                continue
        entities.append(ArcticSpaSwitch(client, sw))

    async_add_entities(entities)


class ArcticSpaSwitch(ArcticSpaEntity, SwitchEntity):
    """Switch entity for spa features."""

    def __init__(self, client: ArcticSpaClient, config: SwitchConfig) -> None:
        super().__init__(client, config.key)
        self._config = config
        self._attr_translation_key = config.translation_key
        self._attr_icon = config.icon

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        if not self._client.live:
            return None
        value = self._client.live.get(self._config.live_key)
        if value is None:
            return None
        # Handle enum values (filter, ozone status)
        if isinstance(value, str):
            return value not in ("FILTER_IDLE", "FILTER_SUSPENDED", "OZONE_IDLE")
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the feature."""
        await self._client.send_command(**{self._config.command_key: True})

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the feature."""
        await self._client.send_command(**{self._config.command_key: False})
