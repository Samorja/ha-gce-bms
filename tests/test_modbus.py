"""Decoding tests for the RBMS status block, using a frame captured from a real cabinet."""

import importlib.util
from pathlib import Path
import sys
import types

# Load the HA-independent modules without importing the integration package (needs homeassistant)
PKG_DIR = Path(__file__).parents[1] / "custom_components" / "gce_bms"
pkg = types.ModuleType("gce_bms")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["gce_bms"] = pkg
for name in ("const", "modbus"):
    spec = importlib.util.spec_from_file_location(f"gce_bms.{name}", PKG_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"gce_bms.{name}"] = module
    spec.loader.exec_module(module)

from gce_bms.modbus import (  # noqa: E402
    PROTECTION_2_EVENTS,
    ModuleData,
    RbmsStatus,
    decode_events,
    module_base,
    ranked_cells,
)

# 0x1100-0x111F read from a cabinet on 2026-10-26 (charging at -10 A, SOC 17 %)
CAPTURED = [
    0x19F6, 0x0011, 0xAAAA, 0x000F, 0x0000, 0x0111, 0xFF9C, 0x0011,
    0x0064, 0x000F, 0x0001, 0x0001, 0x000B, 0x0004, 0x0008, 0x0D01,
    0x0004, 0x0028, 0x0CB4, 0x0003, 0x001C, 0x0000, 0x0000, 0x079F,
    0x000F, 0x0000, 0x000F, 0x0000, 0x000F, 0x0000, 0x0000, 0x0000,
]


def test_decode_captured_frame():
    s = RbmsStatus.from_registers(CAPTURED)
    assert s.voltage == 664.6
    assert s.charge_state == "charging"
    assert s.self_test == "ok"
    assert s.current == -10.0
    assert s.power == -6646.0
    assert s.soc == 17
    assert s.soh == 100
    assert (s.temperature_max, s.temperature_min) == (15, 11)
    assert (s.cell_voltage_max, s.cell_voltage_max_module, s.cell_voltage_max_position) == (3.329, 4, 40)
    assert (s.cell_voltage_min, s.cell_voltage_min_module, s.cell_voltage_min_position) == (3.252, 3, 28)
    assert s.cell_voltage_delta == 77
    assert s.bmu_working == [1, 2, 3, 4]
    assert s.bmu_faults == []
    assert s.self_test_failures == []
    assert (s.breaker, s.main_positive_contactor, s.auxiliary_discharge_contactor) == (
        "closed",
        "closed",
        "closed",
    )
    assert s.negative_contactor == "open"
    assert s.warnings == s.protections_1 == s.protections_2 == []


def test_negative_temperature_and_events():
    regs = list(CAPTURED)
    regs[12] = 0xFFFB  # -5 degC
    regs[21] = 0b1000_0000_0010_0001  # bits 0, 5, 15
    regs[24] = 0x0007  # BMU 4 lost communication
    s = RbmsStatus.from_registers(regs)
    assert s.temperature_min == -5
    assert s.warnings == ["total_voltage_high", "charge_temperature_low", "discharge_temperature_low"]
    assert s.bmu_faults == [4]
    assert decode_events(1 << 7, PROTECTION_2_EVENTS) == ["external_protection"]


# Module 3 block (0x2100-0x217F) captured on 2026-10-26: 50 cells, 24 temperature probes
MODULE_3 = (
    [3336, 3337, 3338, 3337, 3337, 3338, 3338, 3337, 3338, 3338, 3337, 3337, 3337, 3336, 3337, 3338,
     3337, 3335, 3336, 3338, 3335, 3337, 3337, 3337, 3335, 3337, 3336, 3267, 3337, 3337, 3337, 3337,
     3336, 3337, 3335, 3337, 3335, 3335, 3335, 3336, 3337, 3336, 3336, 3336, 3335, 3337, 3336, 3337,
     3337, 3333]
    + [0] * 14
    + [14, 13, 12, 13, 12, 13, 12, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 12]
    + [0] * 40
)


def test_module_layout():
    assert len(MODULE_3) == 0x80
    assert [module_base(m) for m in (1, 2, 3, 4)] == [0x2000, 0x2080, 0x2100, 0x2180]
    m = ModuleData.from_registers(3, MODULE_3)
    assert len(m.voltages) == 50
    assert len(m.temperatures) == 24
    assert m.voltages[27] == 3.267  # cell 28, reported as the cabinet's lowest cell
    assert min(m.voltages) == 3.267
    assert m.temperatures[:3] == [14, 13, 12]


def test_module_negative_temperature_and_empty_module():
    regs = list(MODULE_3)
    regs[0x40] = 0xFFFE
    assert ModuleData.from_registers(3, regs).temperatures[0] == -2
    empty = ModuleData.from_registers(5, [0] * 0x80)
    assert empty.voltages == [] and empty.temperatures == []


def test_ranked_cells():
    m3 = ModuleData.from_registers(3, MODULE_3)
    m4 = ModuleData(module=4, voltages=[3.300, 0.0, 3.400], temperatures=[])
    ranked = ranked_cells({3: m3, 4: m4})
    assert len(ranked) == 52  # the 0 V slot is skipped
    assert ranked[0] == (3.267, 3, 28)
    assert ranked[1] == (3.3, 4, 1)
    assert ranked[-1] == (3.4, 4, 3)
