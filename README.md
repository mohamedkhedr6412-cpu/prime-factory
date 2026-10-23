# PRIME-Factory — Track B (Software) — Phase 0

Industry 4.0 Smart Manufacturing Platform — Software Infrastructure

## Quick Start (Windows)

### Prerequisites
- Python 3.11+
- Mosquitto Broker
- MQTT Explorer (GUI, optional but recommended)

### Setup (first time only)
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python init_db.py

### Run (every session)
Terminal 1 — Broker:
    & "C:\Program Files\mosquitto\mosquitto.exe" -c "C:\prime-factory\config\mosquitto.conf" -v

Terminal 2 — Mock Publisher:
    python firmware/mock_publisher.py normal

### Verify (Milestone M1)
    .\test_mock.ps1
Expected output: "PASS: 100/100 messages received - QoS 1 verified"

## Project Structure
- firmware/mock_publisher.py : ESP32 simulator (5 modes)
- config/mosquitto.conf : Broker configuration
- config/schema.sql : Database schema
- data/factory.db : SQLite database
- docs/INTEGRATION-CONTRACT.md : Signed contract with Track A
- init_db.py : DB initializer
- requirements.txt : Python dependencies
- test_mock.ps1 : QoS 1 test script

## Mock Publisher Modes
- normal — Regular 12s fill cycle (0 → 100g)
- clog — Motor stall (current = 2.8A, weight frozen)
- high_temp — Elevated temperature (72C)
- overweight — Weight overshoot (> 110g)
- brownout — Connection loss every 30s (LWT test)

## Database Tables
- sensor_readings: Time-series (1 row/second)
- production_units: Event-based (1 row/cycle)
- anomalies: PdM alerts
- system_config: Tunable parameters

## MQTT Topics
- prime-factory/data (QoS 1, No Retain)
- prime-factory/status (QoS 1, Retained)
- prime-factory/command (QoS 1, No Retain)
- prime-factory/alerts (QoS 1, No Retain)

## Milestone M1 — Definition of Done
- [x] Mosquitto Broker runs with custom config
- [x] Schema has 4 tables
- [x] Mock Publisher sends 5 modes
- [x] QoS 1 test: 100/100 messages
- [x] Integration Contract signed by Track A + Track B