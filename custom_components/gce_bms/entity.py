"""Base entity for the GCE BMS integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_UNIT_ID, DOMAIN, MANUFACTURER, MODEL
from .coordinator import GceBmsCoordinator


class GceBmsEntity(CoordinatorEntity[GceBmsCoordinator]):
    """Entity bound to one RBMS battery cabinet."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GceBmsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=f"GCE BMS {entry.data[CONF_UNIT_ID]}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            model_id=f"Unit {entry.data[CONF_UNIT_ID]} @ {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        )
