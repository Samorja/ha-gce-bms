"""Sensor platform for the GCE BMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CELLS_PER_MODULE, CONF_TEMPS_PER_MODULE, RANKED_CELLS
from .coordinator import GceBmsCellCoordinator, GceBmsConfigEntry, GceBmsCoordinator
from .entity import GceBmsEntity
from .modbus import CHARGE_STATES, SELF_TEST_STATES, SWITCH_STATES, RbmsStatus, ranked_cells

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
    runtime = entry.runtime_data
    entities: list[SensorEntity] = [
        GceBmsSensor(runtime.status, description) for description in SENSORS
    ]
    if (cells := runtime.cells) is not None:
        cells_per_module = int(entry.options.get(CONF_CELLS_PER_MODULE, 0))
        temps_per_module = int(entry.options.get(CONF_TEMPS_PER_MODULE, 0))
        for module, data in cells.data.items():
            entities.extend(
                GceBmsCellVoltageSensor(cells, module, cell)
                for cell in range(1, (cells_per_module or len(data.voltages)) + 1)
            )
            entities.extend(
                GceBmsCellTemperatureSensor(cells, module, sensor)
                for sensor in range(1, (temps_per_module or len(data.temperatures)) + 1)
            )
        entities.extend(
            cls(cells, highest, rank)
            for cls in (GceBmsRankedCellSensor, GceBmsRankedCellPositionSensor)
            for highest in (False, True)
            for rank in range(1, RANKED_CELLS + 1)
        )

    # Drop cell entities left over from a larger battery layout or disabled cell polling
    keep = {entity.unique_id for entity in entities}
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            reg_entry.domain == SENSOR_DOMAIN
            and any(part in reg_entry.unique_id for part in ("_module_", "_cell_lowest_", "_cell_highest_"))
            and reg_entry.unique_id not in keep
        ):
            registry.async_remove(reg_entry.entity_id)

    async_add_entities(entities)


class GceBmsSensor(GceBmsEntity[GceBmsCoordinator], SensorEntity):
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


class GceBmsCellVoltageSensor(GceBmsEntity[GceBmsCellCoordinator], SensorEntity):
    """Voltage of one cell."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: GceBmsCellCoordinator, module: int, cell: int) -> None:
        super().__init__(coordinator, "cell_voltage", f"module_{module}_cell_{cell}")
        self._attr_translation_placeholders = {"module": str(module), "cell": f"{cell:02d}"}
        self._module = module
        self._index = cell - 1

    @property
    def native_value(self) -> float | None:
        values = self.coordinator.data[self._module].voltages
        return values[self._index] if self._index < len(values) else None


class GceBmsCellTemperatureSensor(GceBmsEntity[GceBmsCellCoordinator], SensorEntity):
    """One temperature probe of a module (disabled by default)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: GceBmsCellCoordinator, module: int, sensor: int) -> None:
        super().__init__(coordinator, "module_temperature", f"module_{module}_temperature_{sensor}")
        self._attr_translation_placeholders = {"module": str(module), "sensor": f"{sensor:02d}"}
        self._module = module
        self._index = sensor - 1

    @property
    def native_value(self) -> int | None:
        values = self.coordinator.data[self._module].temperatures
        return values[self._index] if self._index < len(values) else None


class GceBmsRankedCellSensor(GceBmsEntity[GceBmsCellCoordinator], SensorEntity):
    """N-th lowest or highest cell voltage of the cabinet, with its position as attributes."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: GceBmsCellCoordinator, highest: bool, rank: int) -> None:
        key = "cell_highest" if highest else "cell_lowest"
        super().__init__(coordinator, key, f"{key}_{rank}")
        self._attr_translation_placeholders = {"rank": str(rank)}
        self._highest = highest
        self._rank = rank

    def _cell(self) -> tuple[float, int, int] | None:
        ranked = ranked_cells(self.coordinator.data)
        if self._rank > len(ranked):
            return None
        return ranked[-self._rank] if self._highest else ranked[self._rank - 1]

    @property
    def native_value(self) -> float | None:
        cell = self._cell()
        return cell[0] if cell else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (cell := self._cell()) is None:
            return None
        return {"module": cell[1], "cell": cell[2]}


class GceBmsRankedCellPositionSensor(GceBmsRankedCellSensor):
    """Which cell is the n-th lowest or highest, as "M<module>/C<cell>" for a readable history."""

    _attr_device_class = None
    _attr_state_class = None
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = None

    def __init__(self, coordinator: GceBmsCellCoordinator, highest: bool, rank: int) -> None:
        super().__init__(coordinator, highest, rank)
        key = f"{self._attr_translation_key}_position"
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{key}_{rank}"

    @property
    def native_value(self) -> str | None:
        cell = self._cell()
        return f"M{cell[1]}/C{cell[2]}" if cell else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (cell := self._cell()) is None:
            return None
        return {"module": cell[1], "cell": cell[2], "voltage": cell[0]}
