"""Fan entities for Arctic Spa pumps and blowers."""

from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ArcticSpaEntity
from .spa_client import ArcticSpaClient

# Map percentage to pump speed: 0%=OFF, 50%=LOW, 100%=HIGH
SPEED_MAP = {"OFF": 0, "LOW": 50, "HIGH": 100}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arctic Spa fan entities (pumps and blowers)."""
    client: ArcticSpaClient = entry.runtime_data
    entities: list[FanEntity] = []

    config = client.config or {}

    # Pumps 1-5
    for i in range(1, 6):
        if config.get(f"pump_{i}", True):  # Default to True if no config
            entities.append(ArcticSpaPump(client, i))

    # Blowers 1-2
    for i in range(1, 3):
        if config.get(f"blower_{i}", False):
            entities.append(ArcticSpaBlower(client, i))

    async_add_entities(entities)


class ArcticSpaPump(ArcticSpaEntity, FanEntity):
    """Pump entity with OFF/LOW/HIGH speeds."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_speed_count = 2  # LOW and HIGH

    def __init__(self, client: ArcticSpaClient, pump_number: int) -> None:
        super().__init__(client, f"pump_{pump_number}")
        self._pump_number = pump_number
        self._attr_translation_key = "pump"
        self._attr_translation_placeholders = {"index": str(pump_number)}
        self._attr_icon = "mdi:pump"

    @property
    def is_on(self) -> bool | None:
        """Return True if pump is running."""
        status = self._get_status()
        if status is None:
            return None
        return status != "OFF"

    @property
    def percentage(self) -> int | None:
        """Return speed as percentage."""
        status = self._get_status()
        if status is None:
            return None
        return SPEED_MAP.get(status, 0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set pump speed."""
        if percentage == 0:
            value = 0  # OFF
        elif percentage <= 50:
            value = 1  # LOW
        else:
            value = 2  # HIGH
        await self._client.send_command(
            **{f"set_pump_{self._pump_number}": value}
        )

    async def async_turn_on(
        self, percentage: int | None = None, **kwargs
    ) -> None:
        """Turn on the pump."""
        await self.async_set_percentage(percentage or 100)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the pump."""
        await self.async_set_percentage(0)

    def _get_status(self) -> str | None:
        """Get pump status from live data."""
        if not self._client.live:
            return None
        return self._client.live.get(f"pump_{self._pump_number}")


class ArcticSpaBlower(ArcticSpaEntity, FanEntity):
    """Blower entity with OFF/LOW/HIGH speeds."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_speed_count = 2

    def __init__(self, client: ArcticSpaClient, blower_number: int) -> None:
        super().__init__(client, f"blower_{blower_number}")
        self._blower_number = blower_number
        self._attr_translation_key = "blower"
        self._attr_translation_placeholders = {"index": str(blower_number)}
        self._attr_icon = "mdi:fan"

    @property
    def is_on(self) -> bool | None:
        """Return True if blower is running."""
        status = self._get_status()
        if status is None:
            return None
        return status != "OFF"

    @property
    def percentage(self) -> int | None:
        """Return speed as percentage."""
        status = self._get_status()
        if status is None:
            return None
        return SPEED_MAP.get(status, 0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set blower speed."""
        if percentage == 0:
            value = 0
        elif percentage <= 50:
            value = 1
        else:
            value = 2
        await self._client.send_command(
            **{f"set_blower_{self._blower_number}": value}
        )

    async def async_turn_on(
        self, percentage: int | None = None, **kwargs
    ) -> None:
        """Turn on the blower."""
        await self.async_set_percentage(percentage or 100)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the blower."""
        await self.async_set_percentage(0)

    def _get_status(self) -> str | None:
        """Get blower status from live data."""
        if not self._client.live:
            return None
        return self._client.live.get(f"blower_{self._blower_number}")
