"""
PRIME-Factory v1.0 — Rule-Based AI (Real Mode)
Source: Software Constitution v1.0, Section 15.4 — AI (Anomaly Detection)

Rule-based anomaly detection (Layer 1).
Fast, no false positives, works without ML model.
"""

from backend.serial_reader import SensorReading


class RuleBasedAI:
    """
    Rule-based anomaly detection (Layer 1).
    Fast, no false positives, works without ML model.
    """

    def __init__(self):
        self.current_threshold_a = 0.9  # JAM threshold
        self.temp_threshold_c = 70.0
        self.vibration_threshold_g = 0.15
        self.voltage_low_threshold_v = 9.0

    def check_anomaly(self, reading: SensorReading) -> dict:
        """Check for anomalies based on rules."""
        anomalies = []
        severity = "normal"

        # Current check
        if reading.current_a >= 1.4:
            anomalies.append("INSTANT OVERCURRENT")
            severity = "critical"
        elif reading.current_a >= self.current_threshold_a:
            anomalies.append("JAM DETECTED")
            severity = "high"

        # Temperature check
        if reading.temp_c >= self.temp_threshold_c:
            anomalies.append("OVERTEMPERATURE")
            severity = "critical"

        # Vibration check
        if reading.vib_rms >= self.vibration_threshold_g:
            anomalies.append("HIGH VIBRATION")
            if severity != "critical":
                severity = "high"

        # Voltage check
        if reading.voltage_v <= self.voltage_low_threshold_v and reading.voltage_v > 0.5:
            anomalies.append("UNDERVOLTAGE")
            if severity != "critical":
                severity = "medium"

        return {
            "anomalies": anomalies,
            "severity": severity,
            "has_anomaly": len(anomalies) > 0
        }
