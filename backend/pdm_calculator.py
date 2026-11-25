"""
PRIME-Factory v1.0 — PdM Calculator (Real Mode)
Source: Software Constitution v1.0, Section 15.3 — PdM (Predictive Maintenance)

Calculate PdM metrics from live Arduino data.
"""

from typing import List
from backend.serial_reader import SensorReading


class PdMCalculator:
    """Calculate PdM metrics from live Arduino data."""

    def __init__(self, baseline_vibration_g: float = 0.05):
        self.baseline_vibration_g = baseline_vibration_g
        self.vibration_history: List[float] = []
        self.temp_history: List[float] = []

    def update(self, reading: SensorReading) -> dict:
        """Update PdM metrics with new reading."""
        self.vibration_history.append(reading.vib_rms)
        self.temp_history.append(reading.temp_c)

        # Keep last 60 readings
        if len(self.vibration_history) > 60:
            self.vibration_history.pop(0)
        if len(self.temp_history) > 60:
            self.temp_history.pop(0)

        # Vibration trend
        vib_trend = self._calculate_trend(self.vibration_history)
        vib_ratio = reading.vib_rms / self.baseline_vibration_g if self.baseline_vibration_g > 0 else 0

        # Temperature trend
        temp_trend = self._calculate_trend(self.temp_history)

        # Health score (0-100)
        health_score = self._calculate_health_score(vib_ratio, temp_trend)

        return {
            "vibration_rms_g": round(reading.vib_rms, 3),
            "vibration_baseline_g": self.baseline_vibration_g,
            "vibration_ratio": round(vib_ratio, 2),
            "vibration_trend": vib_trend,
            "temp_c": round(reading.temp_c, 1),
            "temp_trend": temp_trend,
            "health_score": round(health_score, 1),
            "alert_level": self._get_alert_level(vib_ratio, temp_trend)
        }

    def _calculate_trend(self, history: List[float]) -> str:
        """Calculate trend: 'stable', 'increasing', 'decreasing'."""
        if len(history) < 10:
            return "stable"

        recent_avg = sum(history[-10:]) / 10
        older_avg = sum(history[-20:-10]) / 10

        if recent_avg > older_avg * 1.1:
            return "increasing"
        elif recent_avg < older_avg * 0.9:
            return "decreasing"
        else:
            return "stable"

    def _calculate_health_score(self, vib_ratio: float, temp_trend: str) -> float:
        """Calculate health score (0-100)."""
        score = 100.0

        # Vibration penalty
        if vib_ratio > 3.0:
            score -= 50
        elif vib_ratio > 2.0:
            score -= 30
        elif vib_ratio > 1.5:
            score -= 15

        # Temperature trend penalty
        if temp_trend == "increasing":
            score -= 20

        return max(0, score)

    def _get_alert_level(self, vib_ratio: float, temp_trend: str) -> str:
        """Get alert level: 'normal', 'warning', 'critical'."""
        if vib_ratio > 3.0 or (vib_ratio > 2.0 and temp_trend == "increasing"):
            return "critical"
        elif vib_ratio > 1.5 or temp_trend == "increasing":
            return "warning"
        else:
            return "normal"
