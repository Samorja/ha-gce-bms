"""The GCE BMS integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CELL_SCAN_INTERVAL, DEFAULT_CELL_SCAN_INTERVAL
from .coordinator import (
    GceBmsCellCoordinator,
    GceBmsConfigEntry,
    GceBmsCoordinator,
    GceBmsRuntimeData,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GceBmsConfigEntry) -> bool:
    """Set up a GCE BMS battery cabinet from a config entry."""
    status = GceBmsCoordinator(hass, entry)
    await status.async_config_entry_first_refresh()

    cells = None
    if entry.options.get(CONF_CELL_SCAN_INTERVAL, DEFAULT_CELL_SCAN_INTERVAL) > 0:
        # One battery module per working BMU
        cells = GceBmsCellCoordinator(hass, entry, status.client, status.data.bmu_working)
        await cells.async_config_entry_first_refresh()

    entry.runtime_data = GceBmsRuntimeData(status=status, cells=cells)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GceBmsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: GceBmsConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
