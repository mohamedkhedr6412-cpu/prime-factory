# PRIME-Factory — Integration Contract

**Version:** 2.0
**Date:** Saturday, October 26, 2026

## 1. MQTT Topics
| Topic | QoS | Retained | Purpose |
|-------|-----|----------|---------|
| prime-factory/data | 1 | No | Sensor readings (1 Hz) |
| prime-factory/status | 1 | YES | ONLINE / OFFLINE (LWT) |
| prime-factory/command | 1 | No | stop / reset |
| prime-factory/alerts | 1 | No | AI alerts |

## 2. Payload Schema (JSON)
{
  "device": "esp32_station",
  "uptime_ms": 123456,
  "weight": 100.15,
  "current": 0.842,
  "temp": 42.3,
  "status": "FILLING",
  "error": null,
  "motor_current": 0.512,
  "servo_angle": 75
}

- **status**: IDLE | FILLING | SETTLING | COMPLETE | ERROR
- **error**: CLOG | OVERWEIGHT | null

## 3. Database Schema (4 Tables)
- `sensor_readings` (Time-Series)
- `production_units` (Events)
- `anomalies` (PdM)
- `system_config` (Key-Value)

## 4. Signatures
Track A Lead: _______________________
Track B (SW-1): _______________________
Track B (SW-2): _______________________