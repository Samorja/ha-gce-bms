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

from gce_bms.modbus import RbmsStatus, decode_events, PROTECTION_2_EVENTS  # noqa: E402

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
