"""Sensor platform for the Fidbox integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DataUpdateCoordinator
from .const import DOMAIN, MANUFACTURER

SENSORS = [
    SensorEntityDescription(
        key="temperature_1",
        name="Wood temperature (sensor 1)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity_1",
        name="Wood humidity (sensor 1)",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature_2",
        name="Screed temperature (sensor 2)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity_2",
        name="Screed humidity (sensor 2)",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fidbox sensors from a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    async_add_entities(
        FidboxSensorEntity(coordinator, entry, description, address)
        for description in SENSORS
        if description.key in coordinator.data
    )


class FidboxSensorEntity(CoordinatorEntity, SensorEntity):
    """A single sensor of a Fidbox."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        address: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._address = address
        self._attr_unique_id = f"{address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={("bluetooth", address)},
            name=coordinator.data.get("local_name", "Fidbox"),
            manufacturer=MANUFACTURER,
            model="Fidbox",
        )

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Show the timestamp of the last measurement as an attribute."""
        ts = self.coordinator.data.get("measurement_time")
        return {"last_measurement": ts.isoformat()} if ts else None
