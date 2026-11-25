"""
PRIME-Factory v1.0 — MES Calculator (Real Mode)
Source: Software Constitution v1.0, Section 15.1 — MES (Manufacturing Execution System)

Calculate MES metrics from live Arduino data.
"""

from typing import List
from backend.serial_reader import SensorReading


class MESCalculator:
    """Calculate MES metrics from live Arduino data."""

    def __init__(self):
        self.units_total = 0
        self.cycle_start_time = None
        self.cycle_times: List[float] = []
        self.setpoint_rpm = 220

    def update(self, reading: SensorReading):
        """Update MES metrics with new reading."""
        # Count units (every 8 pulses = 1 revolution = 1 unit)
        # This is already done in Arduino firmware
        self.units_total = reading.units

        # Calculate cycle time (time per revolution)
        if reading.rpm > 0:
            cycle_time_s = 60.0 / reading.rpm
            self.cycle_times.append(cycle_time_s)
            # Keep last 60 cycle times
            if len(self.cycle_times) > 60:
                self.cycle_times.pop(0)

        # OEE Calculation
        availability = self._calculate_availability()
        performance = self._calculate_performance(reading.rpm)
        quality = self._calculate_quality(reading.current_a)
        oee = availability * performance * quality

        return {
            "units_total": self.units_total,
            "avg_cycle_time_s": (
                sum(self.cycle_times) / len(self.cycle_times) if self.cycle_times else 0
            ),
            "oee_pct": round(oee * 100, 1),
            "availability_pct": round(availability * 100, 1),
            "performance_pct": round(performance * 100, 1),
            "quality_pct": round(quality * 100, 1)
        }

    def _calculate_availability(self) -> float:
        """Availability = Run Time / Planned Time."""
        # Simplified: assume 100% availability if running
        return 1.0

    def _calculate_performance(self, actual_rpm: float) -> float:
        """Performance = (Ideal Cycle Time × Total Units) / Run Time."""
        if self.setpoint_rpm == 0:
            return 0
        return min(actual_rpm / self.setpoint_rpm, 1.0)

    def _calculate_quality(self, current_a: float) -> float:
        """Quality = Good Units / Total Units."""
        # Assume quality is good if current is within normal range
        if 0.02 <= current_a <= 0.10:  # Normal operating range
            return 1.0
        elif current_a > 0.10:
            return 0.9  # Slight degradation
        else:
            return 0.5  # Idle or fault
