# ha_fidbox — Home Assistant integration for the Metrinova Fidbox

Custom integration for the [Fidbox](https://fidbox.nl/fidbox) by Metrinova: a
battery-powered Bluetooth sensor with two humidity/temperature sensors (wood
side and screed side) for hardwood flooring.

## BLE protocol (reverse-engineered)

Metrinova does not publish an API or GATT specification. The protocol was
determined through BLE sniffing:

| Part | UUID | Content |
|---|---|---|
| Service | `1bc5f1d0-0200-b79a-e411-f2a6c0a4ddc9` | Fidbox service |
| Measurement | `1bc5f1d7-0200-b79a-e411-f2a6c0a4ddc9` | 14 bytes, read + notify |
| Battery | `1bc5f1da-0200-b79a-e411-f2a6c0a4ddc9` | 1 byte, percentage |

Measurement characteristic payload:

```
byte 0-5   : timestamp (year-2000, month, day, hour, minute, second)
byte 6-7   : temperature sensor 1 (uint16 BIG-endian, 1/1000 °C)
byte 8-9   : relative humidity sensor 1 (uint16 BIG-endian, 1/1000 %)
byte 10-11 : temperature sensor 2 (uint16 BIG-endian, 1/1000 °C)
byte 12-13 : relative humidity sensor 2 (uint16 BIG-endian, 1/1000 %)
```

> ⚠️ **Status: calibration in progress.** The scale (1/1000) and byte order
> were derived from multiple measurements and produce plausible room
> temperatures, but final alignment with the official Fidbox app is still
> ongoing. See `tools/test_fidbox3.py` for the calibration procedure.

## Installation

1. Copy the "custom_components/fidbox" folder to the Home Assistant
   configuration directory:

```
<config>/custom_components/fidbox/
```

   where "<config>" is your HA configuration directory (e.g. "/config"
   on HAOS or "/homeassistant" on a Raspberry Pi).

2. Restart Home Assistant.

3. Go to **Settings → Devices & Services → Add Integration** and search for
   **Fidbox**. Make sure the Fidbox is awake and Bluetooth is active (built-in
   adapter or an ESPHome Bluetooth proxy). The integration also auto-discovers
   the device: as soon as the Fidbox advertises, a discovery notification
   appears in the UI.

## Entities

Up to 5 sensors are created per Fidbox:

| Entity | Description |
|---|---|
| Wood temperature (sensor 1) | °C, top side of the Fidbox |
| Wood humidity (sensor 1) | % RH wood side |
| Screed temperature (sensor 2) | °C, cavity below the Fidbox |
| Screed humidity (sensor 2) | % RH screed side |
| Battery | % |

Each sensor has the attribute "last_measurement" with the measurement
timestamp from the device.

## Configuration

When adding the integration you can set the polling interval (default
900 s). Keep battery life in mind: do not poll more often than necessary.

## Tools

The "tools/" directory contains test scripts (require
"pip install bleak"):

- "sniff_fidbox.py" — generic BLE/GATT sniffer.
- "test_fidbox2.py" — targeted readout of measurement + battery, with BE/LE comparison.
- "test_fidbox3.py" — calibration test: repeated reads, all characteristics
  and simultaneous measurement against the Fidbox app.

## Known limitations

- Active readout (connect) only, no passive advertisement parsing: the
  advertisements contain no measurement values.
- The Fidbox drops the BLE connection itself after a short time; the
  integration therefore connects briefly per polling cycle.
- The Fidbox stores historical measurements in the device; only the current
  values are read out.
