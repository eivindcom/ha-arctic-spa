"""Switch entities for Arctic Spa."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.restore_state import RestoreEntity

from .entity import ArcticSpaEntity
from .spa_client import ArcticSpaClient

# Eco mode lowers setpoint by this many degrees Fahrenheit (5°C ≈ 9°F)
ECO_OFFSET_F = 9


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

    # Always add eco mode switch
    entities.append(ArcticSpaEcoSwitch(client))

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


class ArcticSpaEcoSwitch(ArcticSpaEntity, SwitchEntity, RestoreEntity):
    """Eco mode switch that lowers the setpoint by 5°C to save energy.

    When activated, saves the current setpoint and lowers it by 5°C.
    When deactivated, restores the original setpoint.
    Survives HA restarts via RestoreEntity.
    """

    _attr_translation_key = "eco_mode"
    _attr_icon = "mdi:leaf"

    def __init__(self, client: ArcticSpaClient) -> None:
        super().__init__(client, "eco_mode")
        self._is_on = False
        self._saved_setpoint_f: int | None = None

    async def async_added_to_hass(self) -> None:
        """Restore state on HA restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._is_on = last_state.state == "on"
            # Restore saved setpoint from attributes
            saved = last_state.attributes.get("saved_setpoint_f")
            if saved is not None:
                self._saved_setpoint_f = int(saved)

    @property
    def is_on(self) -> bool:
        """Return True if eco mode is active."""
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict:
        """Store saved setpoint for restore after HA restart."""
        attrs = {}
        if self._saved_setpoint_f is not None:
            attrs["saved_setpoint_f"] = self._saved_setpoint_f
            attrs["saved_setpoint_c"] = round(
                (self._saved_setpoint_f - 32) * 5 / 9, 1
            )
        return attrs

    async def async_turn_on(self, **kwargs) -> None:
        """Activate eco mode: save setpoint and lower by 5°C."""
        current_f = self._client.temperature_setpoint_fahrenheit
        if current_f is None:
            return

        self._saved_setpoint_f = current_f
        target_f = max(current_f - ECO_OFFSET_F, 80)  # Don't go below 80°F (26.7°C)
        await self._client.send_command(
            set_temperature_setpoint_fahrenheit=target_f
        )
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Deactivate eco mode: restore original setpoint."""
        if self._saved_setpoint_f is not None:
            await self._client.send_command(
                set_temperature_setpoint_fahrenheit=self._saved_setpoint_f
            )
            self._saved_setpoint_f = None
        self._is_on = False
        self.async_write_ha_state()
