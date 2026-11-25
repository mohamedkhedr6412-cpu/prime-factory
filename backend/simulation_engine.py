"""
PRIME-Factory v1.0 — Simulation Engine
Source: Software Constitution v1.0, Section 11 — Simulation Engine

Generates realistic time-series data for a specific machine + fault.
Two modes: 'without_pf' (catastrophic failure) and 'with_pf' (early detection).
"""

import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from backend.machine_profiles import MACHINE_PROFILES


class SimulationEngine:
    """
    Generates realistic time-series data for a specific machine + fault.
    Two modes: 'without_pf' (catastrophic failure) and 'with_pf' (early detection).
    """

    def __init__(self, machine_id: str, fault_id: str, duration_s: int = 60):
        self.machine = MACHINE_PROFILES[machine_id]
        self.fault = self.machine["faults"][fault_id]
        self.duration_s = duration_s
        self.injection_time_s = self.fault["injection_time_s"]

    def generate_without_pf(self) -> List[Dict]:
        """
        Timeline A: No PRIME-Factory.
        Fault progresses → catastrophic failure → high losses.
        """
        data = []
        baseline_rpm = self.machine["rated_rpm"]
        baseline_current = self.machine["rated_current_a"] * self.machine["typical_load_pct"]
        baseline_vib = self.machine["baseline_vibration_g"]
        baseline_temp = self.machine["baseline_temp_c"]

        for t in range(self.duration_s):
            if t < self.injection_time_s:
                # Normal operation
                rpm = baseline_rpm + random.uniform(-5, 5)
                current = baseline_current + random.uniform(-0.5, 0.5)
                vib = baseline_vib + random.uniform(-0.01, 0.01)
                temp = baseline_temp + random.uniform(-0.5, 0.5)
                state = "RUNNING"
            else:
                # Fault progression (gradual degradation)
                fault_duration = t - self.injection_time_s
                progress = fault_duration / (self.duration_s - self.injection_time_s)

                # RPM drops gradually
                rpm = baseline_rpm * (1 - progress * 0.8) + random.uniform(-10, 10)

                # Current spikes (with noise)
                current_spike = self.fault["current_spike_a"] - baseline_current
                current = baseline_current + current_spike * progress + random.uniform(-1, 1)

                # Vibration increases
                vib = baseline_vib * (1 + self.fault["vibration_increase_factor"] * progress)
                vib += random.uniform(-0.02, 0.02)

                # Temperature rises
                temp = baseline_temp + self.fault["temp_increase_rate_c_per_min"] * (fault_duration / 60) * 10
                temp += random.uniform(-0.5, 0.5)

                state = "RUNNING"
                if progress > 0.9:
                    state = "FAULT"
                    rpm = 0
                    current = self.fault["current_spike_a"]

            data.append({
                "t_s": t,
                "timestamp": (datetime.now() + timedelta(seconds=t)).isoformat(),
                "rpm": round(max(0, rpm), 1),
                "current_a": round(max(0, current), 2),
                "voltage_v": round(380 + random.uniform(-5, 5), 1),
                "power_w": round(current * 380 * 0.85 / 1000, 2),
                "temp_c": round(temp, 1),
                "vibration_rms_g": round(max(0, vib), 3),
                "energy_wh": round(current * 380 * 0.85 / 3600, 4),
                "units_produced": int(
                    self.machine["production_rate_units_per_hour"] / 3600 * t * (rpm / baseline_rpm)
                ),
                "oee_pct": round(85 * (rpm / baseline_rpm), 1),
                "state": state,
                "alert": None
            })

        return data

    def generate_with_pf(self) -> List[Dict]:
        """
        Timeline B: With PRIME-Factory.
        Early detection → planned maintenance → minimal losses.
        """
        data = []
        baseline_rpm = self.machine["rated_rpm"]
        baseline_current = self.machine["rated_current_a"] * self.machine["typical_load_pct"]
        baseline_vib = self.machine["baseline_vibration_g"]
        baseline_temp = self.machine["baseline_temp_c"]

        # Detection time (much earlier)
        detection_time_s = int(self.fault["time_to_detection_with_pf_min"] * 60)
        # Never exceed 50% of the timeline, otherwise detection happens
        # after the scenario ends and Phase B shows no alert at all.
        detection_time_s = min(detection_time_s, int(self.duration_s * 0.5))
        if detection_time_s < 5:
            detection_time_s = 5  # Minimum 5 seconds for demo

        for t in range(self.duration_s):
            if t < self.injection_time_s:
                # Normal operation
                rpm = baseline_rpm + random.uniform(-5, 5)
                current = baseline_current + random.uniform(-0.5, 0.5)
                vib = baseline_vib + random.uniform(-0.01, 0.01)
                temp = baseline_temp + random.uniform(-0.5, 0.5)
                state = "RUNNING"
                alert = None
            elif t < self.injection_time_s + detection_time_s:
                # Fault starts but not yet detected
                fault_duration = t - self.injection_time_s
                progress = fault_duration / detection_time_s

                rpm = baseline_rpm * (1 - progress * 0.1) + random.uniform(-5, 5)
                current = baseline_current + (self.fault["current_spike_a"] - baseline_current) * progress * 0.3
                vib = baseline_vib * (1 + self.fault["vibration_increase_factor"] * progress * 0.5)
                temp = baseline_temp + self.fault["temp_increase_rate_c_per_min"] * (fault_duration / 60)
                state = "RUNNING"
                alert = None
            else:
                # Detected! System alerts, maintenance planned
                rpm = baseline_rpm + random.uniform(-2, 2)  # Back to normal after maintenance
                current = baseline_current + random.uniform(-0.3, 0.3)
                vib = baseline_vib + random.uniform(-0.01, 0.01)
                temp = baseline_temp + random.uniform(-0.3, 0.3)
                state = "RUNNING"
                alert = (
                    f"⚠ {self.fault['name']} detected at t="
                    f"{self.injection_time_s + detection_time_s}s. Planned maintenance initiated."
                )

            data.append({
                "t_s": t,
                "timestamp": (datetime.now() + timedelta(seconds=t)).isoformat(),
                "rpm": round(max(0, rpm), 1),
                "current_a": round(max(0, current), 2),
                "voltage_v": round(380 + random.uniform(-3, 3), 1),
                "power_w": round(current * 380 * 0.85 / 1000, 2),
                "temp_c": round(temp, 1),
                "vibration_rms_g": round(max(0, vib), 3),
                "energy_wh": round(current * 380 * 0.85 / 3600, 4),
                "units_produced": int(
                    self.machine["production_rate_units_per_hour"] / 3600 * t
                ),
                "oee_pct": round(85 * (rpm / baseline_rpm), 1),
                "state": state,
                "alert": alert
            })

        return data
