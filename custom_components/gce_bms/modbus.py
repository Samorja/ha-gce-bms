"""Minimal async Modbus TCP client and RBMS register decoding.

Kept free of Home Assistant imports so it can be tested standalone.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import itertools
import struct

from .const import (
    CELL_BLOCK_SIZE,
    CELL_SLOTS,
    REG_CONFIG_COUNT,
    REG_CONFIG_START,
    MODULE_STRIDE,
    REG_CELL_START,
    REG_STATUS_COUNT,
    REG_STATUS_START,
)

# Several cabinets often share one RS485-to-Ethernet gateway; serialise access per gateway.
_LOCKS: dict[tuple[str, int], asyncio.Lock] = {}
_TRANSACTION_IDS = itertools.count(1)


class ModbusError(Exception):
    """Base error for Modbus communication."""


class ModbusConnectionError(ModbusError):
    """Could not connect or the device did not answer."""


class ModbusExceptionResponse(ModbusError):
    """The device answered with a Modbus exception."""

    def __init__(self, code: int) -> None:
        super().__init__(f"Modbus exception code {code}")
        self.code = code


class GceBmsClient:
    """Reads holding registers over Modbus TCP."""

    def __init__(self, host: str, port: int, unit_id: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        """Read `count` holding registers starting at `address` (function 0x03)."""
        return (await self.read_blocks([(address, count)]))[0]

    async def read_blocks(self, blocks: list[tuple[int, int]]) -> list[list[int]]:
        """Read several (address, count) blocks over one TCP connection."""
        lock = _LOCKS.setdefault((self.host, self.port), asyncio.Lock())
        async with lock:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
            except (TimeoutError, OSError) as err:
                raise ModbusConnectionError(
                    f"Cannot connect to {self.host}:{self.port}: {err!r}"
                ) from err
            try:
                return [
                    await asyncio.wait_for(self._request(reader, writer, address, count), self.timeout)
                    for address, count in blocks
                ]
            except (TimeoutError, OSError, asyncio.IncompleteReadError) as err:
                raise ModbusConnectionError(
                    f"No response from {self.host}:{self.port} unit {self.unit_id}: {err!r}"
                ) from err
            finally:
                writer.close()
                with suppress(OSError):
                    await writer.wait_closed()

    async def _request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        address: int,
        count: int,
    ) -> list[int]:
        tid = next(_TRANSACTION_IDS) & 0xFFFF
        writer.write(struct.pack(">HHHBBHH", tid, 0, 6, self.unit_id, 0x03, address, count))
        await writer.drain()

        # Skip stale frames from earlier timed-out requests
        while True:
            r_tid, _proto, length, _unit = struct.unpack(">HHHB", await reader.readexactly(7))
            body = await reader.readexactly(length - 1)
            if r_tid == tid:
                break

        if body[0] & 0x80:
            raise ModbusExceptionResponse(body[1])
        byte_count = body[1]
        if byte_count != count * 2 or len(body) < 2 + byte_count:
            raise ModbusError(f"Unexpected response length {byte_count} for {count} registers")
        return list(struct.unpack(f">{count}H", body[2 : 2 + byte_count]))

    async def read_status(self) -> RbmsStatus:
        """Read and decode the cabinet status block."""
        return RbmsStatus.from_registers(
            await self.read_holding_registers(REG_STATUS_START, REG_STATUS_COUNT)
        )

    async def read_config(self) -> BmsConfig:
        """Read capacity, layout and protection thresholds."""
        return BmsConfig.from_registers(
            await self.read_holding_registers(REG_CONFIG_START, REG_CONFIG_COUNT)
        )

    async def read_modules(self, modules: list[int]) -> dict[int, ModuleData]:
        """Read cell voltages and temperatures of the given (1-based) modules."""
        blocks = [
            (module_base(module) + offset, CELL_BLOCK_SIZE)
            for module in modules
            for offset in range(0, MODULE_STRIDE, CELL_BLOCK_SIZE)
        ]
        results = await self.read_blocks(blocks)
        per_module = MODULE_STRIDE // CELL_BLOCK_SIZE
        return {
            module: ModuleData.from_registers(
                module,
                [v for block in results[i * per_module : (i + 1) * per_module] for v in block],
            )
            for i, module in enumerate(modules)
        }


def _s16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def _bits(value: int) -> list[int]:
    """1-based indexes of set bits."""
    return [i + 1 for i in range(16) if value >> i & 1]


CHARGE_STATES = {0x0011: "charging", 0x0022: "discharging", 0x0033: "idle"}
SELF_TEST_STATES = {0xAAAA: "ok", 0xBBBB: "failed"}
SWITCH_STATES = {0: "open", 1: "closed", 2: "fault"}

# Table 1: warning events (register 0x1115)
WARNING_EVENTS = (
    "total_voltage_high",
    "total_voltage_low",
    "charge_overcurrent",
    "discharge_overcurrent",
    "charge_temperature_high",
    "charge_temperature_low",
    "bmu_communication_failure",
    None,
    "temperature_imbalance",
    "cell_imbalance",
    "soc_low",
    "insulation_low",
    "cell_voltage_high",
    "cell_voltage_low",
    "discharge_temperature_high",
    "discharge_temperature_low",
)

# Table 2: primary protection events, contactor opened (register 0x1116)
PROTECTION_1_EVENTS = (
    "total_voltage_high",
    "total_voltage_low",
    "charge_overcurrent",
    "discharge_overcurrent",
    "charge_temperature_high",
    "charge_temperature_low",
    "bmu_communication_failure",
    None,
    "temperature_imbalance",
    "insulation_low",
    "cell_imbalance",
    "soc_low",
    "cell_voltage_high",
    "cell_voltage_low",
    "discharge_temperature_high",
    "discharge_temperature_low",
)

# Table 4: secondary protection events, circuit breaker tripped (register 0x111E)
PROTECTION_2_EVENTS = (
    "total_voltage_high",
    "total_voltage_low",
    "charge_overcurrent",
    "discharge_overcurrent",
    "charge_temperature_high",
    "charge_temperature_low",
    None,
    "external_protection",
    "temperature_imbalance",
    "insulation_low",
    "cell_imbalance",
    "soc_low",
    "cell_voltage_high",
    "cell_voltage_low",
    "discharge_temperature_high",
    "discharge_temperature_low",
)

# Table 3: BMS detailed self-test bits (register 0x1117)
SELF_TEST_DETAIL = ("hall_sensor", "ethernet", "memory_chip", "bmu_supply_voltage")


def decode_events(value: int, table: tuple[str | None, ...]) -> list[str]:
    """Names of active events in a bit field."""
    return [table[i] or f"bit_{i}" for i in range(16) if value >> i & 1]


@dataclass(slots=True)
class RbmsStatus:
    """Decoded status of one RBMS battery cabinet."""

    voltage: float
    charge_state: str | None
    charge_state_raw: int
    self_test: str | None
    self_test_raw: int
    bmu_working: list[int]
    breaker: str | None
    main_positive_contactor: str | None
    auxiliary_discharge_contactor: str | None
    negative_contactor: str | None
    switch_raw: int
    current: float
    soc: int
    soh: int
    temperature_max: int
    temperature_max_module: int
    temperature_max_position: int
    temperature_min: int
    temperature_min_module: int
    temperature_min_position: int
    cell_voltage_max: float
    cell_voltage_max_module: int
    cell_voltage_max_position: int
    cell_voltage_min: float
    cell_voltage_min_module: int
    cell_voltage_min_position: int
    warning_raw: int
    protection_1_raw: int
    self_test_detail_raw: int
    bmu_communication_ok: list[int]
    bmu_voltage_ok: list[int]
    bmu_temperature_ok: list[int]
    protection_2_raw: int
    negative_half_current: float
    warnings: list[str] = field(default_factory=list)
    protections_1: list[str] = field(default_factory=list)
    protections_2: list[str] = field(default_factory=list)

    @property
    def power(self) -> float:
        """Battery power in W, positive = discharging."""
        return round(self.voltage * self.current, 1)

    @property
    def cell_voltage_delta(self) -> int:
        """Difference between highest and lowest cell in mV."""
        return round((self.cell_voltage_max - self.cell_voltage_min) * 1000)

    @property
    def bmu_count(self) -> int:
        return len(self.bmu_working)

    @property
    def bmu_faults(self) -> list[int]:
        """BMUs that work but report a communication, voltage or temperature fault."""
        return sorted(
            n
            for n in self.bmu_working
            if n not in self.bmu_communication_ok
            or n not in self.bmu_voltage_ok
            or n not in self.bmu_temperature_ok
        )

    @property
    def self_test_failures(self) -> list[str]:
        return [
            name
            for i, name in enumerate(SELF_TEST_DETAIL)
            if not self.self_test_detail_raw >> i & 1
        ]

    @classmethod
    def from_registers(cls, r: list[int]) -> RbmsStatus:
        """Decode registers 0x1100-0x111F."""
        if len(r) < REG_STATUS_COUNT:
            raise ValueError(f"Expected {REG_STATUS_COUNT} registers, got {len(r)}")
        sw = r[5]
        return cls(
            voltage=round(r[0] * 0.1, 1),
            charge_state=CHARGE_STATES.get(r[1]),
            charge_state_raw=r[1],
            self_test=SELF_TEST_STATES.get(r[2]),
            self_test_raw=r[2],
            bmu_working=_bits(r[3]) + [n + 16 for n in _bits(r[4])],
            breaker=SWITCH_STATES.get(sw & 0xF),
            main_positive_contactor=SWITCH_STATES.get(sw >> 4 & 0xF),
            auxiliary_discharge_contactor=SWITCH_STATES.get(sw >> 8 & 0xF),
            negative_contactor=SWITCH_STATES.get(sw >> 12 & 0xF),
            switch_raw=sw,
            current=round(_s16(r[6]) * 0.1, 1),
            soc=r[7],
            soh=r[8],
            temperature_max=_s16(r[9]),
            temperature_max_module=r[10],
            temperature_max_position=r[11],
            temperature_min=_s16(r[12]),
            temperature_min_module=r[13],
            temperature_min_position=r[14],
            cell_voltage_max=r[15] / 1000,
            cell_voltage_max_module=r[16],
            cell_voltage_max_position=r[17],
            cell_voltage_min=r[18] / 1000,
            cell_voltage_min_module=r[19],
            cell_voltage_min_position=r[20],
            warning_raw=r[21],
            protection_1_raw=r[22],
            self_test_detail_raw=r[23],
            bmu_communication_ok=_bits(r[24]) + [n + 16 for n in _bits(r[25])],
            bmu_voltage_ok=_bits(r[26]) + [n + 16 for n in _bits(r[27])],
            bmu_temperature_ok=_bits(r[28]) + [n + 16 for n in _bits(r[29])],
            protection_2_raw=r[30],
            negative_half_current=round(_s16(r[31]) * 0.1, 1),
            warnings=decode_events(r[21], WARNING_EVENTS),
            protections_1=decode_events(r[22], PROTECTION_1_EVENTS),
            protections_2=decode_events(r[30], PROTECTION_2_EVENTS),
        )


def module_base(module: int) -> int:
    """First register of a (1-based) module's cell data."""
    return REG_CELL_START + (module - 1) * MODULE_STRIDE


def _trim_zeros(values: list[int]) -> list[int]:
    """Drop unused (zero) slots at the end."""
    end = len(values)
    while end and values[end - 1] == 0:
        end -= 1
    return values[:end]


@dataclass(slots=True)
class ModuleData:
    """Cell voltages (V) and temperatures (degC) of one battery module."""

    module: int
    voltages: list[float]
    temperatures: list[int]

    @classmethod
    def from_registers(cls, module: int, r: list[int]) -> ModuleData:
        """Decode one module block: CELL_SLOTS cell voltages (mV), then temperatures."""
        return cls(
            module=module,
            voltages=[v / 1000 for v in _trim_zeros(r[:CELL_SLOTS])],
            temperatures=[_s16(v) for v in _trim_zeros(r[CELL_SLOTS:MODULE_STRIDE])],
        )


def ranked_cells(modules: dict[int, ModuleData]) -> list[tuple[float, int, int]]:
    """All reporting cells as (voltage, module, cell) sorted from lowest to highest voltage."""
    return sorted(
        (voltage, module, index + 1)
        for module, data in modules.items()
        for index, voltage in enumerate(data.voltages)
        if voltage > 0
    )


# (group, scale) in register order from 0x5004; each group holds THRESHOLD_LEVELS values
THRESHOLD_GROUPS = (
    ("cell_overvoltage", 0.001),
    ("cell_undervoltage", 0.001),
    ("total_overvoltage", 0.1),
    ("total_undervoltage", 0.1),
    ("charge_overcurrent", 0.1),
    ("discharge_overcurrent", 0.1),
)
THRESHOLD_LEVELS = ("warning", "protection_1", "protection_2", "recovery")


@dataclass(slots=True)
class BmsConfig:
    """Rated capacity, layout and protection thresholds (V or A)."""

    capacity_ah: int
    module_count: int
    cells_per_module: int
    thresholds: dict[str, float]

    @classmethod
    def from_registers(cls, r: list[int]) -> BmsConfig:
        """Decode registers 0x5000-0x501B."""
        if len(r) < REG_CONFIG_COUNT:
            raise ValueError(f"Expected {REG_CONFIG_COUNT} registers, got {len(r)}")
        thresholds = {}
        for g, (group, scale) in enumerate(THRESHOLD_GROUPS):
            for lvl, level in enumerate(THRESHOLD_LEVELS):
                thresholds[f"{group}_{level}"] = round(r[4 + g * 4 + lvl] * scale, 3)
        return cls(capacity_ah=r[0], module_count=r[1], cells_per_module=r[2], thresholds=thresholds)
