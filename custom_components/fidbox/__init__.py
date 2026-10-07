"""Fidbox (Metrinova) BLE sensor integration for Home Assistant.

Protocol (determined through BLE reverse engineering):
  Service    : 1bc5f1d0-0200-b79a-e411-f2a6c0a4ddc9
  Measurement: 1bc5f1d7-0200-b79a-e411-f2a6c0a4ddc9 (read + notify, 14 bytes)
               byte 0-5  : timestamp (year-2000, month, day, hour, minute, second)
               byte 6-7  : temperature sensor 1 (uint16 BIG-endian, 1/1000 C)
               byte 8-9  : relative humidity sensor 1 (uint16 BIG-endian, 1/1000 %)
               byte 10-11: temperature sensor 2 (uint16 BIG-endian, 1/1000 C)
               byte 12-13: relative humidity sensor 2 (uint16 BIG-endian, 1/1000 %)
  Battery    : 1bc5f1da-0200-b79a-e411-f2a6c0a4ddc9 (1 byte, %)

Calibration: the raw temperature values read over BLE are consistently
~4.5 C higher than the values shown by the official Fidbox app and by an
independent reference thermometer (verified over three days). A fixed
temperature offset (default -4.5 C) is applied to both temperature
channels. The offset is configurable per device via the integration
options. Humidity values are NOT corrected: the Fidbox is mounted inside
the floor construction (between the wooden floor and the concrete
screed), so its humidity readings describe the cavity microclimate and
are meaningful as-is.

Device behaviour: the Fidbox sleeps most of the time and only wakes up
briefly. Connections must be established through
bleak_retry_connector.establish_connection() with the
BleakClientWithServiceCache client class, using a device from the
CONNECTABLE discovery history only - habluetooth can only build a
working connection via a connectable path (a non-connectable entry
crashes the callback wiring). A device seen only by a non-connectable
scanner (e.g. a Shelly) cannot be connected to at all; in that case the
poll simply waits for the next attempt. This integration therefore:
  - establishes connections via bleak_retry_connector, connectable only;
  - retries the connection several times per poll, spread over a few
    minutes to catch a wake window;
  - does not fail setup if the first poll cannot reach the device.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakError
from bleak_retry_connector import BleakClient, establish_connection
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_TEMP_OFFSET,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_TEMP_OFFSET,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ("sensor",)

FIDBOX_SERVICE_UUID = "1bc5f1d0-0200-b79a-e411-f2a6c0a4ddc9"
DATA_CHAR_UUID = "1bc5f1d7-0200-b79a-e411-f2a6c0a4ddc9"
BATTERY_CHAR_UUID = "1bc5f1da-0200-b79a-e411-f2a6c0a4ddc9"

BLE_TIMEOUT = 20.0
CONNECT_ATTEMPTS = 5          # connection attempts per poll
CONNECT_RETRY_DELAY = 25.0    # seconds between attempts (spans wake windows)


def parse_fidbox_data(data: bytes, temp_offset: float = DEFAULT_TEMP_OFFSET) -> dict[str, Any]:
    """Parse the measurement values from the Fidbox data characteristic.

    A fixed temperature offset (default -4.5 C, see module docstring) is
    applied to both temperature channels. Humidity values are returned
    uncorrected.
    """
    if len(data) < 14:
        raise UpdateFailed(f"Payload too short for parsing: {data.hex()}")
    try:
        timestamp = datetime(
            2000 + data[0], data[1], data[2], data[3], data[4], data[5]
        )
    except ValueError as err:
        timestamp = None
        _LOGGER.debug("Invalid timestamp in payload: %s (%s)", data.hex(), err)

    def u16(i: int) -> float:
        return int.from_bytes(data[i:i + 2], "big", signed=False) / 1000.0

    return {
        "temperature_1": u16(6) + temp_offset,
        "humidity_1": u16(8),
        "temperature_2": u16(10) + temp_offset,
        "humidity_2": u16(12),
        "measurement_time": timestamp,
    }


def _get_option(entry: ConfigEntry, key: str, default: Any) -> Any:
    """Read an option, falling back to entry data and a default."""
    return entry.options.get(key, entry.data.get(key, default))


def _find_connectable_ble_device(hass: HomeAssistant, address: str):
    """Look up the BLE device in the CONNECTABLE discovery history only.

    Do NOT fall back to the non-connectable history here: habluetooth
    can only establish a working connection via a connectable path.
    Trying to connect to a non-connectable entry crashes its callback
    wiring ("the first argument must be callable"). If the device is
    currently only visible to non-connectable scanners, there is no way
    to connect to it anyway - the caller should just wait and retry.
    """
    return bluetooth.async_ble_device_from_address(hass, address, connectable=True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Fidbox from a config entry."""
    address = entry.unique_id
    scan_interval = _get_option(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
    temp_offset = float(_get_option(entry, CONF_TEMP_OFFSET, DEFAULT_TEMP_OFFSET))

    async def _async_read_once(ble_device) -> dict[str, Any] | None:
        """Try one connection and read; return None on failure."""
        client: BleakClient | None = None
        try:
            # IMPORTANT: use the BleakClient from bleak_retry_connector
            # (BleakClientWithServiceCache) and let Home Assistant route
            # the connection via the correct Bluetooth backend (USB
            # adapter or ESPHome proxy). Argument order:
            # (client_class, device, hass, name).
            client = await establish_connection(
                BleakClient,
                ble_device,
                hass,
                "fidbox " + address,
                max_attempts=1,
                timeout=BLE_TIMEOUT,
            )
            data = await client.read_gatt_char(DATA_CHAR_UUID)
            battery: int | None = None
            try:
                batt_bytes = await client.read_gatt_char(BATTERY_CHAR_UUID)
                battery = batt_bytes[0]
            except (BleakError, asyncio.TimeoutError, OSError) as err:
                _LOGGER.debug("Failed to read battery: %s", err)
        except (BleakError, asyncio.TimeoutError, OSError, FileNotFoundError) as err:
            _LOGGER.debug("Connection attempt failed for %s: %s", address, err)
            if client is not None:
                try:
                    await client.disconnect()
                except BleakError:
                    pass
            return None
        finally:
            if client is not None and client.is_connected:
                try:
                    await client.disconnect()
                except BleakError:
                    pass

        _LOGGER.debug("Fidbox %s raw data: %s", address, data.hex())
        parsed = parse_fidbox_data(data, temp_offset=temp_offset)
        parsed["local_name"] = ble_device.name or "Fidbox"
        if battery is not None:
            parsed["battery"] = battery
        return parsed

    async def _async_update() -> dict[str, Any]:
        for attempt in range(1, CONNECT_ATTEMPTS + 1):
            # Re-look up the device every attempt: the BLE cache updates
            # continuously and a fresh entry may appear mid-poll.
            ble_device = _find_connectable_ble_device(hass, address)
            if ble_device is not None:
                result = await _async_read_once(ble_device)
                if result is not None:
                    if attempt > 1:
                        _LOGGER.info("Fidbox %s read succeeded on attempt %d", address, attempt)
                    return result
            else:
                # Device not in the connectable history right now: it is
                # either asleep or only seen by non-connectable scanners.
                _LOGGER.debug(
                    "Fidbox %s: no connectable path on attempt %d/%d",
                    address, attempt, CONNECT_ATTEMPTS,
                )

            if attempt < CONNECT_ATTEMPTS:
                # Wait for the next wake/advertising window.
                await asyncio.sleep(CONNECT_RETRY_DELAY)

        raise UpdateFailed(
            f"Could not read Fidbox {address} after {CONNECT_ATTEMPTS} attempts "
            f"(device sleeps most of the time and needs a connectable scanner, "
            f"e.g. an ESPHome proxy, within range)"
        )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Fidbox {address}",
        update_method=_async_update,
        update_interval=timedelta(seconds=int(scan_interval)),
    )

    # Do not block setup on the first successful read: the Fidbox is only
    # reachable during short wake windows, so the first poll may miss it.
    # Setup succeeds and the coordinator keeps retrying on its interval.
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001 - device may be asleep during setup
        _LOGGER.warning(
            "Fidbox %s not reachable yet (%s); will keep retrying on the poll interval",
            address,
            err,
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register the device.
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        identifiers={(DOMAIN, address)},
        manufacturer=MANUFACTURER,
        name="Fidbox " + (address[-5:].replace(":", "") if address else "Fidbox"),
        model="Fidbox",
    )

    # HA removed async_forward_platforms; the modern API is
    # async_forward_entry_setups (available since 2024.7).
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
