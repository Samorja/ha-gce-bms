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
- Configurable polling interval (default 10 s), reconfigure flow for host / port / unit ID
- English and Slovak translations

All values come from one read of registers `0x1100–0x111F` per poll.

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

Add the integration once per cabinet. Requests to the same gateway are serialised.

The gateway must run in **Modbus TCP** mode (Modbus TCP ↔ RTU conversion), RS485 side 9600 baud, 8N1.

## Notes and limitations

- Only **RBMS** (single cabinet) data is supported. The system-level SBMS (unit `0x30`) is not.
- The BMS answers at most `0x24` registers per request.
- On the tested firmware the registers `0x1120–0x1123` (charge/discharge enable, max power) do not match the protocol document, so they are not exposed.
- Per-cell voltages (`0x2000+`) are not exposed yet: on the tested cabinet a module holds about 50 cells, which does not match the 24 + 8 layout in the document.

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

## Development

```bash
pip install pytest
pytest
```

The tests decode a status frame captured from a real cabinet.

## License

MIT
