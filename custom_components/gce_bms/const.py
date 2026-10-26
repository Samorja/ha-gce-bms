"""Constants for the GCE BMS integration."""

from __future__ import annotations

DOMAIN = "gce_bms"

CONF_UNIT_ID = "unit_id"

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

MANUFACTURER = "GCE"
MODEL = "RBMS"

# RBMS single battery cabinet status block (protocol GCE015 V1.2, chapter 5.2)
REG_STATUS_START = 0x1100
REG_STATUS_COUNT = 32  # 0x1100-0x111F, the BMS answers at most 0x24 registers per request
