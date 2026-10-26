"""Constants for the GCE BMS integration."""

from __future__ import annotations

DOMAIN = "gce_bms"

CONF_UNIT_ID = "unit_id"
CONF_CELL_SCAN_INTERVAL = "cell_scan_interval"
CONF_MODULE_COUNT = "module_count"  # 0 = one module per working BMU
CONF_CELLS_PER_MODULE = "cells_per_module"  # 0 = cells that report a voltage

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_CELL_SCAN_INTERVAL = 60  # 0 disables per-cell data
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

MANUFACTURER = "GCE"
MODEL = "RBMS"

# RBMS single battery cabinet status block (protocol GCE015 V1.2, chapter 5.2)
REG_STATUS_START = 0x1100
REG_STATUS_COUNT = 32  # 0x1100-0x111F, the BMS answers at most 0x24 registers per request

# Battery data (chapter 5.3). The document describes 24 cells + 8 temperatures per module,
# but real firmware uses 0x80 registers per module: 64 cell slots (mV), then 64 temperature
# slots (degC); unused slots read 0.
REG_CELL_START = 0x2000
MODULE_STRIDE = 0x80
CELL_SLOTS = 0x40
CELL_BLOCK_SIZE = 0x20
MAX_MODULES = 32  # BMU status bit fields cover 32 BMUs
