"""Config flow for Arctic Spa integration."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST

from .const import DOMAIN
from .spa_client import ArcticSpaClient

_LOGGER = logging.getLogger(__name__)


class ArcticSpaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Arctic Spa."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> dict:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            # Check for duplicate
            self._async_abort_entries_match({CONF_HOST: host})

            # Test connection
            client = ArcticSpaClient(host)
            try:
                connected = await asyncio.wait_for(
                    client.connect(), timeout=10
                )
                if connected:
                    # Wait for initial data
                    for _ in range(5):
                        await asyncio.sleep(1)
                        if client.live is not None:
                            break
                    await client.disconnect()

                    return self.async_create_entry(
                        title="Arctic Spa",
                        data=user_input,
                    )
                errors["base"] = "cannot_connect"
            except asyncio.TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            finally:
                await client.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): str}
            ),
            errors=errors,
        )
