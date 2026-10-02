<p align="center">
  <img src="https://raw.githubusercontent.com/w035h/ha_fidbox/main/assets/logo.svg" alt="Fidbox for Home Assistant" width="400">
</p>

<h3 align="center">Home Assistant integration for the Metrinova Fidbox</h3>

<p align="center">
  <a href="https://github.com/w035h/ha_fidbox/commits/main"><img src="https://img.shields.io/github/last-commit/w035h/ha_fidbox" alt="Last commit"></a>
  <a href="https://github.com/w035h/ha_fidbox/blob/main/LICENSE"><img src="https://img.shields.io/github/license/w035h/ha_fidbox" alt="License"></a>
  <a href="https://github.com/w035h/ha_fidbox/releases"><img src="https://img.shields.io/github/v/release/w035h/ha_fidbox?display_name=tag" alt="Release"></a>
  <img src="https://img.shields.io/badge/HA-2024.8%2B-41BDF5" alt="Home Assistant 2024.8+">
  <img src="https://img.shields.io/badge/protocol-reverse--engineered-FF7043" alt="Protocol reverse-engineered">
</p>

---

Custom integration for the [Fidbox](https://fidbox.nl/fidbox) by Metrinova: a
battery-powered Bluetooth sensor with two humidity/temperature sensors (wood
side and screed side) for hardwood flooring.

## Features

- Automatic discovery — a notification appears as soon as the Fidbox advertises
- 5 sensors: wood temperature and humidity, screed temperature and humidity, battery
- `last_measurement` attribute with the measurement timestamp from the device
- Battery-friendly: short BLE connections, configurable polling interval
- Fully local — no cloud, no app required

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

### Via HACS (recommended)

1. HACS → ⋮ → **Custom repositories**
2. Add "https://github.com/w035h/ha_fidbox" as category **Integration**
3. Search for "Fidbox" in HACS and install
4. Restart Home Assistant

### Manual

1. Copy the "custom_components/fidbox" folder to:

```
<config>/custom_components/fidbox/
```

2. Restart Home Assistant.

### Setup

Go to **Settings → Devices & Services → Add Integration** and search for
**Fidbox**. Make sure the Fidbox is awake and Bluetooth is active (built-in
adapter or an ESPHome Bluetooth proxy). The integration also auto-discovers
the device: as soon as the Fidbox advertises, a discovery notification
appears in the UI.

## Entities

| Entity | Description |
|---|---|
| Wood temperature (sensor 1) | °C, top side of the Fidbox |
| Wood humidity (sensor 1) | % RH wood side |
| Screed temperature (sensor 2) | °C, cavity below the Fidbox |
| Screed humidity (sensor 2) | % RH screed side |
| Battery | % |

## Configuration

When adding the integration you can set the polling interval (default
900 s). Keep battery life in mind: do not poll more often than necessary.

## Tools

The "tools/" directory contains test scripts (require
"pip install bleak"):

- "sniff_fidbox.py" — generic BLE/GATT sniffer
- "test_fidbox2.py" — targeted readout of measurement + battery, with BE/LE comparison
- "test_fidbox3.py" — calibration test: repeated reads, all characteristics
  and simultaneous measurement against the Fidbox app

## Known limitations

- Active readout (connect) only, no passive advertisement parsing: the
  advertisements contain no measurement values.
- The Fidbox drops the BLE connection itself after a short time; the
  integration therefore connects briefly per polling cycle.
- The Fidbox stores historical measurements in the device; only the current
  values are read out.

## License

MIT — see [LICENSE](LICENSE).
