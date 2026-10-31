# GCE BMS for Home Assistant

Custom integration for **GCE RBMS** battery cabinets (protocol *GCE015 – RS485 Protocol BMS with PCS/UPS, V1.2*), read over **Modbus TCP** through an RS485-to-Ethernet gateway.

No YAML, no extra Python dependencies – set up from the UI, one entry per battery cabinet.

## Features

- Voltage, current, power (positive = discharging, compatible with the Energy dashboard), state of charge, state of health
- Charge state (charging / discharging / idle)
- Highest / lowest cell voltage and temperature, with the module and position as attributes, and the cell voltage difference
- Warnings, primary protections (contactor opened) and secondary protections (breaker tripped), decoded into named events
- Circuit breaker and contactor states, BMS self-test, BMU count and BMU communication / voltage / temperature faults
- `Problem` binary sensor that turns on for any warning, protection, failed self-test or BMU fault
- **Voltage of every cell** (e.g. 4 modules × 50 cells = 200 sensors) and every module temperature probe (disabled by default)
- Separate polling intervals for cabinet values (default 10 s) and cell data (default 60 s, `0` turns cell data off)
- Reconfigure flow for host / port / unit ID
- English and Slovak translations

Cabinet values come from one read of registers `0x1100–0x111F`. Cell data is read for each working BMU (one module per BMU) over a single TCP connection.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/Samorja/ha-gce-bms`, type **Integration**.
2. Install **GCE BMS** and restart Home Assistant.

### Manual

Copy `custom_components/gce_bms` into your `config/custom_components/` folder and restart Home Assistant.

## Setup

**Settings → Devices & services → Add integration → GCE BMS**

| Field | Value |
|---|---|
| Host | IP address of the RS485-to-Ethernet gateway |
| Port | `502` (Modbus TCP) |
| Modbus unit ID | Cabinet number: cabinet 1 = `1`, cabinet 2 = `2`, … |

| Number of modules | `0` = automatic (one module per working BMU), or a fixed number |
| Cells per module | `0` = automatic (cells that report a voltage), or a fixed number (max. 64) |
| Temperature probes per module | `0` = automatic (probes that report a value), or a fixed number (max. 64) |

Add the integration once per cabinet. Requests to the same gateway are serialised.

The module, cell and temperature probe counts and both polling intervals can be changed later under **Configure**. If you lower a count, the cell sensors that no longer exist are removed.

The gateway must run in **Modbus TCP** mode (Modbus TCP ↔ RTU conversion), RS485 side 9600 baud, 8N1.

## Notes and limitations

- Only **RBMS** (single cabinet) data is supported. The system-level SBMS (unit `0x30`) is not.
- The BMS answers at most `0x24` registers per request.
- Cell data (`0x2000+`) does not follow the 24 cells + 8 temperatures layout in the document. Real firmware uses `0x80` registers per module: 64 cell voltage slots (mV), then 64 temperature slots (°C). Module *n* starts at `0x2000 + (n−1)·0x80`, and unused slots read `0`. The integration creates sensors only for the cells and probes in use.
- Configuration and protection thresholds are not at `0x4000` as documented but at `0x5000–0x501B`: rated capacity (Ah), module count, cells per module, then six groups of four levels (warning, protection 1, protection 2, recovery) for cell over/undervoltage (mV), pack over/undervoltage (0.1 V) and charge/discharge overcurrent (0.1 A). The block is read once an hour. On firmware without it the threshold sensors are simply not created.
- Registers `0x1120–0x112C` and `0x501C–0x5025` respond but their meaning is unknown, so they are not exposed.

## Entities

| Entity | Unit | Notes |
|---|---|---|
| Voltage | V | |
| Current | A | positive = discharging |
| Power | W | positive = discharging |
| State of charge | % | |
| State of health | % | |
| Charge state | – | charging / discharging / idle |
| Highest / lowest temperature | °C | attributes: `module`, `position` |
| Highest / lowest cell voltage | V | attributes: `module`, `position` |
| Cell voltage difference | mV | |
| Active warnings / primary / secondary protections | count | attribute `active`: list of events |
| Self-test | – | diagnostic; attribute `failed_checks` |
| BMU count | – | diagnostic; per-BMU status lists as attributes |
| Circuit breaker, contactors | – | diagnostic; open / closed / fault |
| Problem, Warning, Primary protection, Secondary protection, BMU fault | binary | device class `problem` |
| Module *n* cell *nn* | V | one per cell |
| Module *n* temperature *nn* | °C | one per probe, disabled by default |
| Lowest cell 1–5 / Highest cell 1–5 | V | the five lowest and five highest cells of the cabinet; attributes `module`, `cell` |
| Lowest / Highest cell 1–5 position | – | which cell holds that rank, e.g. `M3/C28` (module 3, cell 28); its history shows when the weakest / strongest cell changed |
| Rated capacity | Ah | diagnostic |
| Cell / pack overvoltage, cell / pack undervoltage, charge / discharge overcurrent – warning, protection 1, protection 2, recovery | V / A | diagnostic; 24 protection thresholds from the BMS |

Recording 200 cell sensors creates a lot of history. To keep the database small, exclude them from the recorder or lengthen the cell polling interval in the integration options.

## Development

```bash
pip install pytest
pytest
```

The tests decode a status frame and a module block captured from a real cabinet.

## License

MIT
