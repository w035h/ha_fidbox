"""Sniffer utility: capture the BLE advertisements and GATT layout of your Fidbox.

Run this on a machine with Bluetooth (e.g. a Raspberry Pi):

    pip install bleak
    python sniff_fidbox.py

The script:
1. scans for 5 minutes for devices with 'Fidbox' in the name and prints the
   full advertising data;
2. then connects and prints all GATT services and characteristics, including
   the raw contents of readable characteristics.
"""
import asyncio
import sys

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

# Scan duration in seconds (5 minutes).
SCAN_DURATION_SECONDS = 300


def _is_fidbox(adv: AdvertisementData) -> bool:
    name = adv.local_name or ""
    return name.lower().startswith("fidbox")


async def scan() -> BLEDevice | None:
    print(f"Scanning {SCAN_DURATION_SECONDS} s for Fidbox...")
    target: BLEDevice | None = None

    def _cb(device: BLEDevice, adv: AdvertisementData) -> None:
        nonlocal target
        if not _is_fidbox(adv):
            return
        print("=" * 60)
        print(f"Name     : {adv.local_name}")
        print(f"Address  : {device.address}")
        print(f"RSSI     : {adv.rssi} dBm")
        print(f"Service data: {adv.service_data}")
        print(f"Manufacturer: {adv.manufacturer_data}")
        print(f"Service UUIDs: {adv.service_uuids}")
        print(f"Platform data: {adv.platform_data}")
        target = target or device

    scanner = BleakScanner(detection_callback=_cb)
    await scanner.start()
    await asyncio.sleep(SCAN_DURATION_SECONDS)
    await scanner.stop()
    return target


async def dump_services(device: BLEDevice) -> None:
    from bleak import BleakClient

    print(f"\nConnecting to {device.address}...")
    async with BleakClient(device, timeout=30.0) as client:
        print(f"Connected: {client.is_connected}")
        for service in client.services:
            print("\nSERVICE:", service.uuid, service.description)
            for char in service.characteristics:
                print("  CHAR:", char.uuid, "|", char.description)
                print("       properties:", ", ".join(char.properties))
                if "read" in char.properties:
                    try:
                        data = await client.read_gatt_char(char.uuid)
                        print("       value (hex):", data.hex(" "))
                        print("       value (raw):", data)
                    except Exception as err:  # noqa: BLE001
                        print("       read failed:", err)


async def main() -> None:
    device = await scan()
    if device is None:
        print("No Fidbox found. Wake up the Fidbox (tap/activate the measure button).")
        sys.exit(1)
    await dump_services(device)


if __name__ == "__main__":
    asyncio.run(main())
