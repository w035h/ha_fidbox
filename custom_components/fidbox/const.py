"""Constants for the Fidbox integration."""
from __future__ import annotations

DOMAIN = "fidbox"
MANUFACTURER = "Metrinova"

# Configuration / options keys.
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TEMP_OFFSET = "temperature_offset"

# Defaults.
DEFAULT_SCAN_INTERVAL_SECONDS = 900
DEFAULT_TEMP_OFFSET = -4.5

# BLE advertisement name prefixes used for discovery.
LOCAL_NAME_PREFIXES = ("FIDBOX",)
