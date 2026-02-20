"""Sensor entities for Arctic Spa."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ArcticSpaEntity
from .spa_client import ArcticSpaClient


@dataclass
class SensorConfig:
    """Configuration for a spa sensor entity."""

    key: str
    translation_key: str
    icon: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    unit: str | None = None
    source: str = "live"  # "live", "info", "config", or "computed"
    live_key: str | None = None  # Key in live data (defaults to key)
    config_check: str | None = None  # Only show if this config key is True


# Always-present sensors
SENSORS: list[SensorConfig] = [
    SensorConfig(
        "water_temperature", "water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTemperature.CELSIUS,
        source="computed",
    ),
    SensorConfig(
        "setpoint_temperature", "setpoint_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=UnitOfTemperature.CELSIUS,
        source="computed",
    ),
    SensorConfig(
        "heater_1_status", "heater_1_status",
        icon="mdi:radiator",
        live_key="heater_1",
        config_check="heater_1",
    ),
    SensorConfig(
        "heater_2_status", "heater_2_status",
        icon="mdi:radiator",
        live_key="heater_2",
        config_check="heater_2",
    ),
    SensorConfig(
        "filter_status", "filter_status",
        icon="mdi:air-filter",
        live_key="filter",
        config_check="filter",
    ),
    SensorConfig(
        "ozone_status", "ozone_status",
        icon="mdi:molecule",
        live_key="ozone",
    ),
    SensorConfig(
        "ph", "ph",
        icon="mdi:ph",
        state_class=SensorStateClass.MEASUREMENT,
        unit="pH",
        source="info",
    ),
    SensorConfig(
        "orp", "orp",
        icon="mdi:flash",
        state_class=SensorStateClass.MEASUREMENT,
        unit="mV",
        source="info",
    ),
    SensorConfig(
        "heater_adc", "heater_adc",
        icon="mdi:thermometer-lines",
        live_key="heater_adc",
    ),
    SensorConfig(
        "current_adc", "current_adc",
        icon="mdi:current-ac",
        live_key="current_adc",
    ),
    SensorConfig(
        "powerlines", "powerlines",
        icon="mdi:transmission-tower",
        source="config",
    ),
    SensorConfig(
        "breaker_size", "breaker_size",
        icon="mdi:fuse",
        unit="A",
        source="config",
        live_key="breaker_size",
    ),
    SensorConfig(
        "estimated_power", "estimated_power",
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfPower.KILO_WATT,
        source="computed",
    ),
]

# Estimated power per heater in kW (typical for Arctic Spa ~3kW elements)
HEATER_POWER_KW = 3.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arctic Spa sensor entities."""
    client: ArcticSpaClient = entry.runtime_data
    config = client.config or {}
    entities: list[SensorEntity] = []

    for sensor in SENSORS:
        # Check if hardware is installed
        if sensor.config_check and not config.get(sensor.config_check, True):
            continue
        entities.append(ArcticSpaSensor(client, sensor))

    async_add_entities(entities)


class ArcticSpaSensor(ArcticSpaEntity, SensorEntity):
    """Sensor entity for spa data."""

    def __init__(
        self, client: ArcticSpaClient, config: SensorConfig
    ) -> None:
        super().__init__(client, config.key)
        self._config = config
        self._attr_translation_key = config.translation_key
        if config.icon:
            self._attr_icon = config.icon
        if config.device_class:
            self._attr_device_class = config.device_class
        if config.state_class:
            self._attr_state_class = config.state_class
        if config.unit:
            self._attr_native_unit_of_measurement = config.unit

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        cfg = self._config

        if cfg.source == "computed":
            if cfg.key == "water_temperature":
                return self._client.temperature_celsius
            if cfg.key == "setpoint_temperature":
                return self._client.temperature_setpoint_celsius
            if cfg.key == "estimated_power":
                return self._estimate_power()
            return None

        if cfg.source == "info":
            if not self._client.info:
                return None
            return self._client.info.get(cfg.key)

        if cfg.source == "config":
            if not self._client.config:
                return None
            key = cfg.live_key or cfg.key
            value = self._client.config.get(key)
            # Translate phase enum
            if cfg.key == "powerlines" and isinstance(value, str):
                phase_map = {
                    "TRUE_THREE": "3-phase (true)",
                    "SINGLE": "1-phase",
                    "TWO": "2-phase",
                    "THREE": "3-phase",
                }
                return phase_map.get(value, value)
            return value

        # Default: live data
        if not self._client.live:
            return None
        key = cfg.live_key or cfg.key
        return self._client.live.get(key)

    def _estimate_power(self) -> float | None:
        """Estimate power consumption based on heater status.

        Each heater element draws approximately 3 kW when actively heating.
        WARMUP/COOLDOWN states are counted at half power as the element is
        ramping up or down.
        """
        if not self._client.live:
            return None

        power = 0.0
        for heater in ("heater_1", "heater_2"):
            status = self._client.live.get(heater)
            if status == "HEATING":
                power += HEATER_POWER_KW
            elif status in ("WARMUP", "COOLDOWN"):
                power += HEATER_POWER_KW * 0.5

        return round(power, 1)
