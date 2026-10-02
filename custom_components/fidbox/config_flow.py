"""Config flow for the Fidbox integration.

Supports automatic discovery: as soon as Home Assistant sees a BLE
advertisement with a name starting with "Fidbox", HA starts this flow and a
discovery notification appears in the UI.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SCAN_INTERVAL

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN, LOCAL_NAME_PREFIXES

_LOGGER = logging.getLogger(__name__)


def _is_fidbox(name: str | None) -> bool:
    if not name:
        return False
    return name.startswith(LOCAL_NAME_PREFIXES)


class FidboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Fidbox devices, with automatic discovery."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow with an empty discovered-devices list."""
        self._discovered: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual step: choose a discovered Fidbox."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Fidbox {self._discovered.get(address, address)}",
                data={
                    CONF_ADDRESS: address,
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
                    ),
                },
            )

        # Find Fidbox devices in the Bluetooth discovery cache.
        self._discovered = {}
        for service_info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            if _is_fidbox(service_info.name) and service_info.address not in self._discovered:
                self._discovered[service_info.address] = service_info.name or "Fidbox"

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(self._discovered),
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_SECONDS
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
                }
            ),
            description_placeholders={"count": str(len(self._discovered))},
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Automatic discovery via a BLE advertisement.

        Home Assistant calls this step as soon as a device with a matching
        advertisement appears. For custom integrations without registered
        manifest matching, the Bluetooth integration passes all
        advertisements; we filter here on the Fidbox name.
        """
        if not _is_fidbox(discovery_info.name):
            return self.async_abort(reason="not_fidbox")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovered = {discovery_info.address: discovery_info.name}
        self.context["title_placeholders"] = {"name": discovery_info.name}

        # Continue to the user step with the discovered device preselected.
        return await self.async_step_user()
