"""Constants for the Fidbox integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "fidbox"
MANUFACTURER: Final = "Metrinova"

# The Fidbox advertises with a local name starting with "Fidbox".
LOCAL_NAME_PREFIXES: Final = ("Fidbox", "FIDBOX", "fidbox")

# Default polling interval (an active connection drains the battery, so
# do not poll too often).
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 900  # 15 minutes

CONF_SCAN_INTERVAL: Final = "scan_interval"

# Values we try to read (depending on availability in the protocol).
SENSOR_TEMP_1: Final = "temperature_1"  # wood side (above the Fidbox)
SENSOR_HUM_1: Final = "humidity_1"        # CRH wood side
SENSOR_TEMP_2: Final = "temperature_2"   # screed side (cavity below the Fidbox)
SENSOR_HUM_2: Final = "humidity_2"       # CRH screed side
SENSOR_BATTERY: Final = "battery"

ATTR_MODEL: Final = "model"
