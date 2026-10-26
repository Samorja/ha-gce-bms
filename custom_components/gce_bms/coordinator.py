"""Data update coordinator for the GCE BMS integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_UNIT_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .modbus import GceBmsClient, ModbusError, RbmsStatus

_LOGGER = logging.getLogger(__name__)

type GceBmsConfigEntry = ConfigEntry[GceBmsCoordinator]


class GceBmsCoordinator(DataUpdateCoordinator[RbmsStatus]):
    """Polls one RBMS battery cabinet."""

    config_entry: GceBmsConfigEntry

    def __init__(self, hass: HomeAssistant, entry: GceBmsConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_HOST]} unit {entry.data[CONF_UNIT_ID]}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = GceBmsClient(
            entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_UNIT_ID]
        )

    async def _async_update_data(self) -> RbmsStatus:
        try:
            return await self.client.read_status()
        except ModbusError as err:
            raise UpdateFailed(str(err)) from err
