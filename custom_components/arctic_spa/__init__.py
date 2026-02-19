"""Arctic Spa integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, RECONNECT_DELAY
from .spa_client import ArcticSpaClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type ArcticSpaConfigEntry = ConfigEntry[ArcticSpaClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: ArcticSpaConfigEntry
) -> bool:
    """Set up Arctic Spa from a config entry."""
    host = entry.data[CONF_HOST]
    client = ArcticSpaClient(host)

    if not await client.connect():
        raise ConfigEntryNotReady(f"Unable to connect to spa at {host}")

    # Wait for config data (tells us which hardware is installed)
    for _ in range(5):
        await asyncio.sleep(1)
        if client.config is not None:
            break

    if client.config is None:
        _LOGGER.warning("No configuration received from spa, using defaults")

    entry.runtime_data = client

    # Handle reconnection on disconnect
    async def _handle_reconnect() -> None:
        while not client._connected:
            _LOGGER.info("Attempting to reconnect to spa at %s...", host)
            await asyncio.sleep(RECONNECT_DELAY)
            if await client.connect():
                _LOGGER.info("Reconnected to spa")
                return

    def _on_disconnect() -> None:
        _LOGGER.warning("Lost connection to spa at %s", host)
        hass.async_create_task(_handle_reconnect())

    client.register_disconnect_callback(_on_disconnect)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(lambda: hass.async_create_task(client.disconnect()))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ArcticSpaConfigEntry
) -> bool:
    """Unload Arctic Spa config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        await entry.runtime_data.disconnect()
    return unload_ok
