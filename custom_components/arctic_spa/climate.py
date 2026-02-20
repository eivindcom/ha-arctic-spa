"""Climate (thermostat) entity for Arctic Spa."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ArcticSpaEntity
from .spa_client import ArcticSpaClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Arctic Spa climate entity."""
    client: ArcticSpaClient = entry.runtime_data
    async_add_entities([ArcticSpaClimate(client)])


class ArcticSpaClimate(ArcticSpaEntity, ClimateEntity):
    """Thermostat entity for Arctic Spa temperature control."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.5
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 26.7  # ~80F
    _attr_max_temp = 40.0  # ~104F
    _attr_translation_key = "thermostat"
    _attr_name = None  # Use device name

    def __init__(self, client: ArcticSpaClient) -> None:
        super().__init__(client, "climate")

    @property
    def current_temperature(self) -> float | None:
        """Return the current water temperature."""
        return self._client.temperature_celsius

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._client.temperature_setpoint_celsius

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self._client.live and self._client.live.get("economy"):
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if not self._client.live:
            return HVACAction.OFF
        heater = self._client.live.get("heater_1", "HEATER_IDLE")
        if heater in ("HEATING", "WARMUP"):
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temp_c = kwargs.get(ATTR_TEMPERATURE)
        if temp_c is not None:
            await self._client.set_temperature(temp_c)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode (economy mode not available via protocol)."""
        pass
