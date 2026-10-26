"""Binary sensor platform for the GCE BMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GceBmsConfigEntry, GceBmsCoordinator
from .entity import GceBmsEntity
from .modbus import RbmsStatus

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GceBmsBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a GCE BMS binary sensor."""

    is_on_fn: Callable[[RbmsStatus], bool]


BINARY_SENSORS: tuple[GceBmsBinarySensorDescription, ...] = (
    GceBmsBinarySensorDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda s: bool(
            s.warnings
            or s.protections_1
            or s.protections_2
            or s.self_test != "ok"
            or s.bmu_faults
        ),
    ),
    GceBmsBinarySensorDescription(
        key="warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda s: bool(s.warnings),
    ),
    GceBmsBinarySensorDescription(
        key="protection_1",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda s: bool(s.protections_1),
    ),
    GceBmsBinarySensorDescription(
        key="protection_2",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda s: bool(s.protections_2),
    ),
    GceBmsBinarySensorDescription(
        key="bmu_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda s: bool(s.bmu_faults),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GceBmsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GCE BMS binary sensors."""
    coordinator = entry.runtime_data.status
    async_add_entities(
        GceBmsBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class GceBmsBinarySensor(GceBmsEntity[GceBmsCoordinator], BinarySensorEntity):
    """A GCE BMS binary sensor."""

    entity_description: GceBmsBinarySensorDescription

    def __init__(
        self, coordinator: GceBmsCoordinator, description: GceBmsBinarySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data)
