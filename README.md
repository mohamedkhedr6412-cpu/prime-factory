# PRIME-Factory — Software Platform v1.0

Industry 4.0 Smart Manufacturing Platform — Software Infrastructure  
**Constitution:** PRIME-Factory Software Constitution v1.0 (Complete)  
**Python:** 3.14.7 | **Framework:** Dash + Plotly + Bootstrap

---

## Overview

PRIME-Factory is a dual-mode monitoring dashboard built with Python + Dash/Plotly.
It strictly separates **Real Hardware Mode** (reading live data from Arduino Uno via Serial)
from **Industrial Simulation Mode** (demonstrating the value of PdM/EMS/MES on realistic industrial scenarios).

**Real Mode:** The Arduino sends `V,I,VIB,SPD` to an ESP32-S3, which publishes JSON to
`prime-factory/data` (QoS 1) and `prime-factory/status` (retained + LWT). The dashboard
subscribes via `backend/mqtt_subscriber.py` and stores readings in `data/factory.db`.
`current_a` comes from the ESP payload; `weight`, `temp`, `motor_current` and `servo_angle` stay `NULL` until those sensors are added. KPI cards show the newest received reading with a live/stale hint; charts and calculators still use only readings from the last 5 seconds, so old values are never treated as live. The status badge follows the retained MQTT status/LWT, and vibration is displayed in `m/s²` to match the sensor screen.

**Speed control:** Real Mode has a **LOCAL / REMOTE** selector. `LOCAL` leaves the Arduino potentiometer in charge. `REMOTE` publishes `MODE:R,SPD:0..100` to `prime-factory/control` (QoS 1, retained); the ESP forwards it to the Arduino on `Serial2` and re-confirms it every 5 s. The dashboard offers 100%, 80%, 50%, 0% presets and a custom 0–100 input. Switching back to `LOCAL` publishes `MODE:L,SPD:<last>` so the potentiometer takes over again. Telemetry echoes `control_mode` and `control_speed_pct`, which the card shows as the hardware acknowledgement. `Serial2` keeps ESP GPIO44 (`RXD2`, the path that already worked for telemetry) and moves only the command TX to GPIO17 (`TXD2`); GPIO43 is left for the ESP32-S3 Serial Monitor/UART0. Wiring: Arduino TX (Pin 1) → level shifter → ESP GPIO44, and ESP GPIO17 → Arduino RX (Pin 0), with a common ground.

**Energy log:** Every new reading also accumulates motor energy into `energy_log` using `E(Wh) = V × I × Δt / 3600`. Gaps longer than 60 s are skipped so an offline device does not create a fake spike. The Real Mode page uses a **Show period** selector (Today / This month / This year) and displays only that period's total, Wh sublabel, cost and sample count. Its bar chart shows consumption **inside** the selected period — by hour today, by day this month, or by month this year — with zero-valued buckets for hours/days/months without samples. Peak power, run time and duty cycle remain global logged statistics. The selected breakdown table and CSV export always match the chosen period; Print / Save PDF still isolates the energy card. Example: a 10 W motor running for 30 minutes consumes `10 × 0.5 = 5 Wh = 0.005 kWh`.

**Real Mode navigation:** The Real Hardware Monitor is split into five top tabs: **Overview**, **Speed Control**, **Live Charts**, **Analytics** and **Energy Log**. The header with the MQTT badge and freshness hint stays pinned while scrolling. All panels remain mounted, so live updates, controls, CSV export and print/PDF keep working when switching tabs.

**Visual style:** The dashboard uses a calm slate/teal palette with soft contrast for comfortable long viewing. On the Overview tab, the six live readings are stacked vertically — one labelled card per value — instead of a dense horizontal KPI row.

**Simulation Mode:** Focuses on the **Fertilizer Industry** (3 machines) and **Packaging Industry** (3 machines).
Uses a sequential execution engine: Run "Without PRIME-Factory" → Finish → Run "With PRIME-Factory" → Finish → Display Dynamic Comparison Report.

**Pages:** Opening the app shows only the Home page (`/`). Choose a model there to open its dedicated page:
`/real` for live hardware monitoring or `/simulation` for the industrial simulator. Each page contains
only the components and data belonging to that model, and has a **Home** link to return.

---

## Quick Start (one click)

Double-click **PRIME-Factory** on the Desktop, or run `start-platform.bat` from this folder. The launcher:

1. Makes sure the Mosquitto service is running.
2. Starts the Dash server only if it is not already running.
3. Opens `http://127.0.0.1:8050/real` automatically.

To stop the dashboard later, close the minimized **PRIME-Factory Dashboard** console window. Mosquitto is a Windows service set to **Automatic**, so it is normally already running.

---

## Tech Stack (Python 3.14)

| Component | Version | Source |
|---|---|---|
| Language | Python 3.14.7 | Constitution §8 |
| Framework | dash==4.5.1 | Constitution §8 |
| UI Components | dash-bootstrap-components==1.6.0 | Constitution §8 |
| Charts | plotly==5.24.1 | Constitution §8 |
| Data | pandas>=3.0.0, numpy>=2.0.0 | Constitution §8 |
| Hardware Comms | pyserial==3.5 | Constitution §8 |
| Storage | sqlite3 (stdlib) | Constitution §2.1 |

> ⚠ Note: `pandas==2.2.3` and `numpy==1.26.4` pinned in the constitution are **not installable on Python 3.14** (no `cp314` wheels, source build requires Visual Studio). The `requirements.txt` uses compatible `>=3.0.0` / `>=2.0.0` ranges instead.

---

## Project Structure

```
prime-factory/
├── app.py                          # Dash Dashboard (Main Entry)
├── requirements.txt                # Python dependencies
├── vercel.json                     # Vercel deployment config
├── README.md                       # Run instructions
│
├── backend/
│   ├── __init__.py
│   ├── serial_reader.py            # SensorReading dataclass (shared by calculators)
│   ├── mqtt_subscriber.py          # Real Mode: ESP32 MQTT -> SQLite + energy_log
│   ├── simulation_engine.py        # Simulation Mode: data generator
│   ├── machine_profiles.py         # MACHINE_PROFILES dictionary (6 machines + financial constants)
│   ├── financial_calculator.py     # Dynamic loss calculation (no hardcoded constants)
│   ├── sequential_player.py        # Without/With PF player
│   ├── comparison_engine.py        # Final comparison report
│   ├── mes_calculator.py           # MES metrics (OEE, availability, performance, quality)
│   ├── ems_calculator.py           # EMS metrics (energy, power, Wh/unit)
│   ├── pdm_calculator.py           # PdM metrics (health score, vibration/temp trend)
│   ├── rule_based_ai.py            # Rule-Based AI layer (anomaly detection)
│   ├── scenario_generator.py       # JSON scenario generator (9 scenarios)
│
├── simulation_data/
│   └── scenarios/                  # Pre-computed JSON files (9 total)
│       ├── fertilizer_conveyor_unbalance.json
│       ├── fertilizer_granulator_mechanical_jam.json
│       ├── fertilizer_granulator_thermal_overload.json
│       ├── fertilizer_mixer_voltage_sag.json
│       ├── packaging_filling_speed_droop.json
│       ├── packaging_filling_mechanical_jam.json
│       ├── packaging_capping_unbalance.json
│       ├── packaging_capping_loosening.json
│       └── packaging_labeling_voltage_sag.json
│
├── data/
│   └── cache/                      # Real Mode SQLite cache (last 300 seconds)
│
└── docs/
    └── Software-Constitution/
        └── v1.0-complete.html      # Constitution copy (Constitution §9.1)
```

---

## Quick Start (Windows)

### Prerequisites
- Python 3.14+ 64-bit (tested on 3.15.2)
- Mosquitto broker reachable on the LAN (default `192.168.100.16:1883`; override with `MQTT_HOST`)
- ESP32-S3 gateway powered and publishing to `prime-factory/data`

### Setup (first time only)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python init_db.py
```

### Run (every session)

**Terminal 1 — Start the dashboard:**
```powershell
$env:MQTT_HOST = "127.0.0.1"
.\venv\Scripts\python.exe app.py
```
Then open: http://127.0.0.1:8050  
For the no-typing version, just double-click the Desktop shortcut **PRIME-Factory** (see Quick Start above).

**Real Mode:** Power the ESP32 gateway, click "Enter Real Mode". The badge shows the retained MQTT status (`ONLINE`/`OFFLINE`), and a small hint beside it says whether the KPI data is live or when the last packet arrived. Refresh any already-open Real Mode tab after updating the dashboard so it loads the new callback layout.

For speed control, re-upload both modified sketches. Keep the existing Arduino TX → level shifter → ESP **GPIO44 (`RXD2`)** wire exactly as before, and connect **GPIO17 (`TXD2`)** to Arduino RX (Pin 0). GPIO43 is UART0 TX for the ESP32-S3 Serial Monitor and must not be reused for the command link. Keep a common ground and disconnect the TX wire while uploading firmware over USB.
**Simulation Mode:** Click "Enter Simulation Mode", select Industry → Equipment → Fault → Run Scenario.

---

## Modes

### Real Mode (ESP32 → MQTT)
- Subscribes to `prime-factory/data` (QoS 1, retain=false) and `prime-factory/status` (retained + LWT)
- Publishes speed commands to `prime-factory/control` (QoS 1, retained): `MODE:L|R,SPD:0..100`, with LOCAL/REMOTE selector, presets and custom value
- KPI cards show the newest reading every 1 second; the hint says `Live data • just now` or how many seconds ago the last packet arrived
- Live charts (Current & Voltage, Vibration & Temperature) — last 60 seconds of fresh (≤5 s old) readings only
- MES/EMS/PdM metrics calculated dynamically from live data (RPM/units-based values remain placeholders)
- Rule-Based AI anomaly detection (overcurrent, overtemperature, high vibration, undervoltage)
- Every reading is stored in `data/factory.db`; energy is accumulated in `energy_log`
- Energy log with a Today / Month / Year selector, matching within-period chart and table, cost, peak power, runtime, duty cycle, CSV export and print/PDF
- MQTT status badge: `ONLINE` / `OFFLINE` / `CONNECTING` (from connection status, not from reading age)
- Freshness hint beside the badge: `Live data • just now` or how old the last packet is
- Arduino sends telemetry every 1 s; ESP republishes the last sample every 1 s with `duplicate: true`, which the subscriber ignores for storage and energy

### Simulation Mode (Industrial Scenarios)
- Landing Page → Select Industry (Fertilizer / Packaging)
- Select Equipment → Select Fault Type
- Phase A: "Without PRIME-Factory" — fault progresses to catastrophic failure
- Phase B: "With PRIME-Factory" — early detection, planned maintenance
- Comparison Report: dynamic financial loss calculation per machine/fault profile
- 9 scenarios across 2 industries (Constitution §4.3)

---

## Deployment (Vercel)

See Constitution §18.

1. Push code to GitHub
2. Import repo on Vercel
3. Add `vercel.json` (already present in project root)
4. Real Mode (Serial Port) will **NOT** work on Vercel — use localhost for Real Mode, Vercel for Simulation Mode

---

## Testing Checklist

See Constitution §19 (Final Testing Checklist).

- Real Mode: MQTT status badge, freshness hint, newest-reading KPI cards, live-only charts, LOCAL/REMOTE speed control with presets/custom value, energy log (period selector, within-period chart, tariff, peak/runtime/duty, CSV, print/PDF), 5-minute stability
- Simulation Mode: Landing page, industry/equipment/fault dropdowns, Phase A/B, comparison report, financial accuracy, all 9 scenarios, mobile responsive

---

## Notes

- Real Mode uses the local ESP32-S3 → Mosquitto → SQLite path.
- To speed up updates, `Project-main.ino` now sends telemetry every 1 s with fewer blocking sensor samples, and `project-auxiliary.ino` republishes the last sample every 1 s with `"duplicate": true`; the subscriber ignores duplicate republishes so SQLite and energy are not double counted. Both sketches must be re-uploaded to the boards.
- Never commit `*.db` files; recreate the local DB with `python init_db.py`.
- Constitution reference: `docs/Software-Constitution/v1.0-complete.html`
