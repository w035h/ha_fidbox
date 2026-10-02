"""Fidbox test 3: simultaneous measurement, repeated reads and notify listening.

Goal: determine whether characteristic 1bc5f1d7 provides a fresh measurement
at the moment of reading, and whether characteristics d3/d4/d5/dc contain
additional data.

Procedure (important!):
1. Start this script.
2. As soon as the script prints the measurement: open the Fidbox app
   IMMEDIATELY, refresh the measurement (reconnect/refresh) and note down
   temperature, RH and the measurement timestamp.
3. Paste the script output + the app values here.
"""
import asyncio
import sys
from datetime import datetime

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

SCAN_DURATION_SECONDS = 300
CONNECT_TIMEOUT = 30.0
LISTEN_DURATION_SECONDS = 120

# All characteristics of the Fidbox service.
CHARS = {
    "d3": "1bc5f1d3-0200-b79a-e411-f2a6c0a4ddc9",
    "d4": "1bc5f1d4-0200-b79a-e411-f2a6c0a4ddc9",
    "d5": "1bc5f1d5-0200-b79a-e411-f2a6c0a4ddc9",
    "d6": "1bc5f1d6-0200-b79a-e411-f2a6c0a4ddc9",
    "d7": "1bc5f1d7-0200-b79a-e411-f2a6c0a4ddc9",
    "d8": "1bc5f1d8-0200-b79a-e411-f2a6c0a4ddc9",
    "d9": "1bc5f1d9-0200-b79a-e411-f2a6c0a4ddc9",
    "da": "1bc5f1da-0200-b79a-e411-f2a6c0a4ddc9",
    "db": "1bc5f1db-0200-b79a-e411-f2a6c0a4ddc9",
    "dc": "1bc5f1dc-0200-b79a-e411-f2a6c0a4ddc9",
}
DATA_CHAR_UUID = CHARS["d7"]
NOTIFY_CHARS = [CHARS["d7"], CHARS["d3"], CHARS["d4"]]


def parse_measurement(data: bytes) -> dict:
    """Parse a measurement: 6-byte timestamp + 4x uint16 BE /1000 (to be confirmed)."""
    ts = datetime(2000 + data[0], data[1], data[2], data[3], data[4], data[5])
    vals = [int.from_bytes(data[i:i + 2], "big") for i in range(6, 14, 2)]
    return {
        "timestamp": ts.isoformat(),
        "value_1": vals[0] / 1000.0,
        "value_2": vals[1] / 1000.0,
        "value_3": vals[2] / 1000.0,
        "value_4": vals[3] / 1000.0,
    }


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
    now = datetime.now()
    print(f"Local clock now: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    async with BleakClient(device, timeout=CONNECT_TIMEOUT) as client:
        print(f"Connected: {client.is_connected}\n")

        # 1. Subscribe to notify FIRST (before the device may drop off).
        def _handler(sender, data: bytearray) -> None:
            print(f"  NOTIFY: {bytes(data).hex(' ')}")
            if len(bytes(data)) >= 14:
                try:
                    print(f"    parsed: {parse_measurement(bytes(data))}")
                except Exception:  # noqa: BLE001
                    pass

        for uuid in NOTIFY_CHARS:
            try:
                await client.start_notify(uuid, _handler)
                print(f"Subscribed to notify: {uuid}")
            except Exception as err:  # noqa: BLE001
                print(f"Subscribing to {uuid} failed: {err}")

        # 2. Repeated reads: does the timestamp follow the clock?
        for round_no, wait in enumerate((0, 15, 30), start=1):
            if wait:
                await asyncio.sleep(wait)
            try:
                data = await client.read_gatt_char(DATA_CHAR_UUID)
                print(f"\nMeasurement round {round_no} @ {datetime.now().strftime('%H:%M:%S')}:")
                print(f"  hex: {data.hex(' ')}")
                print(f"  parsed: {parse_measurement(data)}")
            except Exception as err:  # noqa: BLE001
                print(f"\nRound {round_no} read failed: {err}")
                break

        # 3. Read all remaining characteristics (d3/d4/d5/dc failed earlier).
        print("\nAll Fidbox characteristics:")
        for name, uuid in CHARS.items():
            try:
                data = await client.read_gatt_char(uuid)
                print(f"  {name}: {data.hex(' ')}  (raw: {data})")
            except Exception as err:  # noqa: BLE001
                print(f"  {name}: read failed: {err}")

        # 4. Listen for live notifications.
        print(f"\nListening {LISTEN_DURATION_SECONDS} s for notifications...")
        print(">>> NOW OPEN THE FIDBOX APP AND REFRESH THE MEASUREMENT <<<")
        try:
            await asyncio.sleep(LISTEN_DURATION_SECONDS)
        except asyncio.CancelledError:
            pass

    print("\nDone. Paste this output plus the app values (temp, RH, timestamp).")


if __name__ == "__main__":
    asyncio.run(main())
