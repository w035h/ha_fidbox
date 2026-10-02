"""Targeted Fidbox test: read measurement values + battery and listen for live notify.

Based on the GATT dump:
  - 1bc5f1d7 : measurement (14 bytes: 6-byte timestamp + 4x uint16 BIG-endian /1000)
  - 1bc5f1da : battery (1 byte, %)

Run:  pip install bleak && python test_fidbox2.py
Compare the printed values with the official Fidbox app.
"""
import asyncio
import sys
from datetime import datetime

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

SCAN_DURATION_SECONDS = 300
CONNECT_TIMEOUT = 30.0
NOTIFY_DURATION_SECONDS = 60

DATA_CHAR_UUID = "1bc5f1d7-0200-b79a-e411-f2a6c0a4ddc9"
BATTERY_CHAR_UUID = "1bc5f1da-0200-b79a-e411-f2a6c0a4ddc9"


def parse_measurement(data: bytes) -> dict:
    """Parse a measurement: 6-byte timestamp (yy,mm,dd,hh,mm,ss) + 4x uint16 BE /1000."""
    ts = datetime(2000 + data[0], data[1], data[2], data[3], data[4], data[5])
    vals = [
        int.from_bytes(data[i:i + 2], "big", signed=False)
        for i in range(6, 14, 2)
    ]
    return {
        "timestamp": ts.isoformat(),
        "temp_1": vals[0] / 1000.0,
        "hum_1": vals[1] / 1000.0,
        "temp_2": vals[2] / 1000.0,
        "hum_2": vals[3] / 1000.0,
    }


def print_interpretations(data: bytes) -> None:
    """Print all possible readings of the 4 uint16 values."""
    for j, i in enumerate(range(6, 14, 2)):
        be = int.from_bytes(data[i:i + 2], "big", signed=False)
        le = int.from_bytes(data[i:i + 2], "little", signed=False)
        print(f"    value_{j+1}: BE raw={be:5d} /1000={be/1000.0:8.3f}"
              f"   (LE /1000={le/1000.0:8.3f})")


def _is_fidbox(adv: AdvertisementData) -> bool:
    return (adv.local_name or "").lower().startswith("fidbox")


async def scan_for_fidbox() -> BLEDevice:
    print(f"Scanning up to {SCAN_DURATION_SECONDS} s for Fidbox...")
    target: BLEDevice | None = None
    found = asyncio.Event()

    def _cb(device: BLEDevice, adv: AdvertisementData) -> None:
        nonlocal target
        if _is_fidbox(adv) and target is None:
            target = device
            print(f"  Found: {adv.local_name} @ {device.address} (RSSI {adv.rssi})")
            found.set()

    scanner = BleakScanner(detection_callback=_cb)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), timeout=SCAN_DURATION_SECONDS)
    except asyncio.TimeoutError:
        await scanner.stop()
        print("No Fidbox found.")
        sys.exit(1)
    await scanner.stop()
    return target


async def main() -> None:
    device = await scan_for_fidbox()
    print(f"Connecting to {device.address} ...")

    async with BleakClient(device, timeout=CONNECT_TIMEOUT) as client:
        print(f"Connected: {client.is_connected}\n")

        # 1. Read the latest measurement.
        data = await client.read_gatt_char(DATA_CHAR_UUID)
        print(f"Measurement (hex): {data.hex(' ')}  ({len(data)} bytes)")
        parsed = parse_measurement(data)
        for key, value in parsed.items():
            print(f"  {key:10s}: {value}")
        print("  Interpretations (compare with the Fidbox app!):")
        print_interpretations(data)

        # 2. Read the battery.
        try:
            batt = await client.read_gatt_char(BATTERY_CHAR_UUID)
            print(f"\nBattery (hex): {batt.hex(' ')}  -> {batt[0]}% (if percentage)")
        except Exception as err:  # noqa: BLE001
            print(f"\nBattery read failed: {err}")

        # 3. Live measurements via notify.
        print(f"\nListening {NOTIFY_DURATION_SECONDS} s for live measurements...")
        notified: list[bytes] = []

        def _handler(sender, data: bytearray) -> None:
            notified.append(bytes(data))
            print(f"  NOTIFY: {bytes(data).hex(' ')}")
            try:
                p = parse_measurement(bytes(data))
                print(f"    {p['timestamp']}  ->  {p['temp_1']}°C {p['hum_1']}% | "
                      f"{p['temp_2']}°C {p['hum_2']}%")
            except Exception:  # noqa: BLE001
                print("    (parse failed)")

        try:
            await client.start_notify(DATA_CHAR_UUID, _handler)
        except Exception as err:  # noqa: BLE001
            print(f"  Subscribe failed: {err}")

        try:
            await asyncio.sleep(NOTIFY_DURATION_SECONDS)
        except asyncio.CancelledError:
            pass

    print(f"\nDone. {len(notified)} live measurements received.")
    print("Compare the values above with the Fidbox app and paste everything here.")


if __name__ == "__main__":
    asyncio.run(main())
