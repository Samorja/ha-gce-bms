"""Sensor platform for the GCE BMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GceBmsConfigEntry, GceBmsCoordinator
from .entity import GceBmsEntity
from .modbus import CHARGE_STATES, SELF_TEST_STATES, SWITCH_STATES, RbmsStatus

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GceBmsSensorDescription(SensorEntityDescription):
    """Describes a GCE BMS sensor."""

    value_fn: Callable[[RbmsStatus], Any]
    attr_fn: Callable[[RbmsStatus], dict[str, Any]] | None = None


def _switch(key: str, value_fn: Callable[[RbmsStatus], str | None]) -> GceBmsSensorDescription:
    return GceBmsSensorDescription(
        key=key,
        device_class=SensorDeviceClass.ENUM,
        options=list(SWITCH_STATES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=value_fn,
    )


SENSORS: tuple[GceBmsSensorDescription, ...] = (
    GceBmsSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda s: s.voltage,
    ),
    GceBmsSensorDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda s: s.current,
    ),
    GceBmsSensorDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda s: s.power,
    ),
    GceBmsSensorDescription(
        key="soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.soc,
    ),
    GceBmsSensorDescription(
        key="soh",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.soh,
    ),
    GceBmsSensorDescription(
        key="charge_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(CHARGE_STATES.values()),
        value_fn=lambda s: s.charge_state,
    ),
    GceBmsSensorDescription(
        key="temperature_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda s: s.temperature_max,
        attr_fn=lambda s: {
            "module": s.temperature_max_module,
            "position": s.temperature_max_position,
        },
    ),
    GceBmsSensorDescription(
        key="temperature_min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda s: s.temperature_min,
        attr_fn=lambda s: {
            "module": s.temperature_min_module,
            "position": s.temperature_min_position,
        },
    ),
    GceBmsSensorDescription(
        key="cell_voltage_max",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=3,
        value_fn=lambda s: s.cell_voltage_max,
        attr_fn=lambda s: {
            "module": s.cell_voltage_max_module,
            "position": s.cell_voltage_max_position,
        },
    ),
    GceBmsSensorDescription(
        key="cell_voltage_min",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=3,
        value_fn=lambda s: s.cell_voltage_min,
        attr_fn=lambda s: {
            "module": s.cell_voltage_min_module,
            "position": s.cell_voltage_min_position,
        },
    ),
    GceBmsSensorDescription(
        key="cell_voltage_delta",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_fn=lambda s: s.cell_voltage_delta,
    ),
    GceBmsSensorDescription(
        key="warnings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: len(s.warnings),
        attr_fn=lambda s: {"active": s.warnings, "raw": s.warning_raw},
    ),
    GceBmsSensorDescription(
        key="protections_1",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: len(s.protections_1),
        attr_fn=lambda s: {"active": s.protections_1, "raw": s.protection_1_raw},
    ),
    GceBmsSensorDescription(
        key="protections_2",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: len(s.protections_2),
        attr_fn=lambda s: {"active": s.protections_2, "raw": s.protection_2_raw},
    ),
    GceBmsSensorDescription(
        key="self_test",
        device_class=SensorDeviceClass.ENUM,
        options=list(SELF_TEST_STATES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.self_test,
        attr_fn=lambda s: {
            "failed_checks": s.self_test_failures,
            "raw": s.self_test_raw,
            "detail_raw": s.self_test_detail_raw,
        },
    ),
    GceBmsSensorDescription(
        key="bmu_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.bmu_count,
        attr_fn=lambda s: {
            "working": s.bmu_working,
            "communication_ok": s.bmu_communication_ok,
            "voltage_ok": s.bmu_voltage_ok,
            "temperature_ok": s.bmu_temperature_ok,
        },
    ),
    _switch("breaker", lambda s: s.breaker),
    _switch("main_positive_contactor", lambda s: s.main_positive_contactor),
    _switch("auxiliary_discharge_contactor", lambda s: s.auxiliary_discharge_contactor),
    _switch("negative_contactor", lambda s: s.negative_contactor),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GceBmsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GCE BMS sensors."""
    coordinator = entry.runtime_data
    async_add_entities(GceBmsSensor(coordinator, description) for description in SENSORS)


class GceBmsSensor(GceBmsEntity, SensorEntity):
    """A GCE BMS sensor."""

    entity_description: GceBmsSensorDescription

    def __init__(
        self, coordinator: GceBmsCoordinator, description: GceBmsSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data)
