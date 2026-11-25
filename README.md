# PRIME-Factory — Software Platform v1.0

Industry 4.0 Smart Manufacturing Platform — Software Infrastructure  
**Constitution:** PRIME-Factory Software Constitution v1.0 (Complete)  
**Python:** 3.14.7 | **Framework:** Dash + Plotly + Bootstrap

---

## Overview

PRIME-Factory is a dual-mode monitoring dashboard built with Python + Dash/Plotly.
It strictly separates **Real Hardware Mode** (reading live data from Arduino Uno via Serial)
from **Industrial Simulation Mode** (demonstrating the value of PdM/EMS/MES on realistic industrial scenarios).

**Real Mode:** Reflects the physical hardware (GA25-370 Motor, ACS712, ADXL345, DS18B20, TCRT5000).
No ESP32 in this phase.

**Simulation Mode:** Focuses on the **Fertilizer Industry** (3 machines) and **Packaging Industry** (3 machines).
Uses a sequential execution engine: Run "Without PRIME-Factory" → Finish → Run "With PRIME-Factory" → Finish → Display Dynamic Comparison Report.

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
│   ├── serial_reader.py            # Real Mode: Arduino Serial parser (@9600 baud)
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
- Python 3.14 (64-bit)
- Arduino Uno connected (for Real Mode only)

### Setup (first time only)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Run (every session)

**Terminal 1 — Start the dashboard:**
```powershell
.\venv\Scripts\python.exe app.py
```
Then open: http://127.0.0.1:8050

**Real Mode:** Connect Arduino Uno to COM3 (default), click "Enter Real Mode".
**Simulation Mode:** Click "Enter Simulation Mode", select Industry → Equipment → Fault → Run Scenario.

---

## Modes

### Real Mode (Arduino Serial Only)
- Reads CSV payload: `STATE,RPM,UNITS,I_A,V_V,T_C,VIB,SETPOINT` @ 9600 baud
- Live KPI cards updated every 1 second
- Live charts (Current & Voltage, Vibration & Temperature) — last 60 seconds
- MES/EMS/PdM metrics calculated dynamically from live Arduino data
- Rule-Based AI anomaly detection (overcurrent, overtemperature, high vibration, undervoltage)
- SQLite cache at `data/cache/real_mode_cache.db` stores last 300 seconds
- **No ESP32, no MQTT** in this phase (Constitution §2.1)

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

- Real Mode: Serial connection, KPI updates, charts, boot safety, E-Stop, TCRT counting, DS18B20, alerts, 5-minute stability
- Simulation Mode: Landing page, industry/equipment/fault dropdowns, Phase A/B, comparison report, financial accuracy, all 9 scenarios, mobile responsive

---

## Notes

- Old Track B Phase 0 files (MQTT / Mosquitto / ESP32 mock publisher) are **not part** of this constitution and were replaced by the Serial-based Real Mode architecture.
- Constitution reference: `docs/Software-Constitution/v1.0-complete.html`
