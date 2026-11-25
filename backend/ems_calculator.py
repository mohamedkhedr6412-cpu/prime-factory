"""
PRIME-Factory v1.0 — EMS Calculator (Real Mode)
Source: Software Constitution v1.0, Section 15.2 — EMS (Energy Management System)

Calculate EMS metrics from live Arduino data.
"""

from backend.serial_reader import SensorReading


class EMSCalculator:
    """Calculate EMS metrics from live Arduino data."""

    def __init__(self):
        self.energy_wh_total = 0.0
        self.last_reading_time = None
        self.last_current_a = 0.0
        self.last_voltage_v = 0.0

    def update(self, reading: SensorReading) -> dict:
        """Update EMS metrics with new reading."""
        # Calculate energy for this interval
        if self.last_reading_time:
            time_delta_s = (reading.timestamp - self.last_reading_time).total_seconds()
            # E = V × I × t / 3600 (Wh)
            energy_wh = (reading.voltage_v * reading.current_a * time_delta_s) / 3600.0
            self.energy_wh_total += energy_wh

        self.last_reading_time = reading.timestamp
        self.last_current_a = reading.current_a
        self.last_voltage_v = reading.voltage_v

        # Wh per unit
        wh_per_unit = self.energy_wh_total / reading.units if reading.units > 0 else 0

        return {
            "energy_wh_total": round(self.energy_wh_total, 4),
            "wh_per_unit": round(wh_per_unit, 4),
            "current_a": round(reading.current_a, 3),
            "voltage_v": round(reading.voltage_v, 2),
            "power_w": round(reading.voltage_v * reading.current_a, 2)
        }
