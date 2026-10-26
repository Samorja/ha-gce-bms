"""Config flow for the GCE BMS integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CELL_SLOTS,
    CONF_CELL_SCAN_INTERVAL,
    CONF_CELLS_PER_MODULE,
    CONF_MODULE_COUNT,
    CONF_TEMPS_PER_MODULE,
    CONF_UNIT_ID,
    DEFAULT_CELL_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MAX_MODULES,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REG_STATUS_START,
    TEMPERATURE_SLOTS,
)
from .coordinator import GceBmsConfigEntry
from .modbus import GceBmsClient, ModbusConnectionError, ModbusError

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any], with_layout: bool = False) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
            **(_layout_schema(defaults) if with_layout else {}),
        }
    )


def _count_selector(maximum: int) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=maximum, step=1, mode=selector.NumberSelectorMode.BOX
        )
    )


def _layout_schema(defaults: Mapping[str, Any]) -> dict[vol.Marker, Any]:
    """Module and cell counts; 0 = detect automatically."""
    return {
        vol.Required(
            CONF_MODULE_COUNT, default=defaults.get(CONF_MODULE_COUNT, 0)
        ): _count_selector(MAX_MODULES),
        vol.Required(
            CONF_CELLS_PER_MODULE, default=defaults.get(CONF_CELLS_PER_MODULE, 0)
        ): _count_selector(CELL_SLOTS),
        vol.Required(
            CONF_TEMPS_PER_MODULE, default=defaults.get(CONF_TEMPS_PER_MODULE, 0)
        ): _count_selector(TEMPERATURE_SLOTS),
    }


async def _validate(data: dict[str, Any]) -> str | None:
    """Return an error key, or None if the cabinet answers."""
    client = GceBmsClient(data[CONF_HOST], data[CONF_PORT], data[CONF_UNIT_ID])
    try:
        await client.read_holding_registers(REG_STATUS_START, 1)
    except ModbusConnectionError:
        return "cannot_connect"
    except ModbusError:
        return "invalid_response"
    except Exception:
        _LOGGER.exception("Unexpected error while connecting to GCE BMS")
        return "unknown"
    return None


class GceBmsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for one RBMS battery cabinet."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT_ID]}"
            )
            self._abort_if_unique_id_configured()
            if (error := await _validate(user_input)) is None:
                data = {k: user_input[k] for k in (CONF_HOST, CONF_PORT, CONF_UNIT_ID)}
                options = {
                    k: int(user_input[k])
                    for k in (CONF_MODULE_COUNT, CONF_CELLS_PER_MODULE, CONF_TEMPS_PER_MODULE)
                }
                return self.async_create_entry(
                    title=f"GCE BMS {user_input[CONF_UNIT_ID]}", data=data, options=options
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}, with_layout=True),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT_ID]}"
            )
            if self.unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()
            if (error := await _validate(user_input)) is None:
                return self.async_update_reload_and_abort(
                    entry, unique_id=self.unique_id, data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: GceBmsConfigEntry) -> GceBmsOptionsFlow:
        return GceBmsOptionsFlow()


class GceBmsOptionsFlow(OptionsFlow):
    """Polling intervals and battery layout."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    **_layout_schema(self.config_entry.options),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_CELL_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_CELL_SCAN_INTERVAL, DEFAULT_CELL_SCAN_INTERVAL
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
