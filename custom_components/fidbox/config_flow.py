"""Config flow and options flow for the Fidbox integration.

Supports automatic discovery: as soon as Home Assistant sees a BLE
advertisement with a name starting with "FIDBOX" or carrying the Fidbox
service UUID, HA starts this flow and a discovery notification appears
in the UI.

Note: the Fidbox often advertises as non-connectable (connectable=False)
while still accepting connections at other moments. The flow therefore
does NOT filter on connectable devices and queries both the connectable
and non-connectable discovery history - doing otherwise makes the
device invisible in the manual flow.

The options flow allows changing the poll interval and the per-device
temperature calibration offset.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TEMP_OFFSET,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_TEMP_OFFSET,
    DOMAIN,
    LOCAL_NAME_PREFIXES,
)

_LOGGER = logging.getLogger(__name__)

FIDBOX_SERVICE_UUID = "1bc5f1d0-0200-b79a-e411-f2a6c0a4ddc9"


def _is_fidbox_name(name: str | None) -> bool:
    if not name:
        return False
    return name.startswith(LOCAL_NAME_PREFIXES)


def _is_fidbox(service_info: Any) -> bool:
    """Match on advertised name or the Fidbox service UUID.

    The Fidbox sometimes advertises without a name, but it always
    includes its service UUID in the advertisement.
    """
    if _is_fidbox_name(service_info.name):
        return True
    return FIDBOX_SERVICE_UUID in [
        uuid.lower() for uuid in getattr(service_info, "service_uuids", []) or []
    ]


def _discover_fidboxes(hass) -> dict[str, str]:
    """Find Fidbox devices in both discovery histories.

    The Fidbox regularly advertises as non-connectable, which places it
    in the non-connectable history only. Querying only the connectable
    history makes the device invisible in the manual flow.
    """
    discovered: dict[str, str] = {}
    for connectable in (True, False):
        for service_info in bluetooth.async_discovered_service_info(
            hass, connectable=connectable
        ):
            if not _is_fidbox(service_info):
                continue
            if service_info.address not in discovered:
                discovered[service_info.address] = service_info.name or "Fidbox"
    return discovered


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

        self._discovered = _discover_fidboxes(self.hass)

        if not self._discovered:
            # Show a helpful screen instead of a bare abort: the Fidbox
            # only advertises around its daily sync/wake moment, so users
            # need to know how to make it visible.
            return self.async_show_form(step_id="no_devices_found")

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

    async def async_step_no_devices_found(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Shown when no Fidbox was found; lets the user retry."""
        return await self.async_step_user()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Automatic discovery via a BLE advertisement."""
        if not _is_fidbox(discovery_info):
            return self.async_abort(reason="not_fidbox")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovered = {discovery_info.address: discovery_info.name or "Fidbox"}
        self.context["title_placeholders"] = {"name": discovery_info.name or "Fidbox"}

        # Continue to the user step with the discovered device preselected.
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> FidboxOptionsFlow:
        """Create the options flow."""
        return FidboxOptionsFlow()


class FidboxOptionsFlow(OptionsFlow):
    """Options flow: poll interval and temperature calibration offset."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        current_offset = self.config_entry.options.get(
            CONF_TEMP_OFFSET,
            self.config_entry.data.get(CONF_TEMP_OFFSET, DEFAULT_TEMP_OFFSET),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                        description={
                            "suggested_value": current_interval,
                        },
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
                    vol.Optional(
                        CONF_TEMP_OFFSET,
                        default=current_offset,
                    ): vol.All(vol.Coerce(float), vol.Range(min=-20.0, max=20.0)),
                }
            ),
        )
