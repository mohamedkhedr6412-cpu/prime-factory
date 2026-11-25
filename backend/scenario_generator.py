"""
PRIME-Factory v1.0 — Scenario Generator
Source: Software Constitution v1.0, Section 16.1 — Scenario Generator

يولّد ملفات JSON واقعية بناءً على MACHINE_PROFILES.
كل سيناريو = ملف JSON واحد يحتوي على 60-120 نقطة بيانات (نقطة لكل ثانية).
"""

import json
import math
import random
from pathlib import Path
from backend.machine_profiles import MACHINE_PROFILES


def generate_scenario(machine_id: str, fault_id: str, duration_s: int = 60) -> dict:
    """Generate realistic time-series data for a specific machine + fault."""
    machine = MACHINE_PROFILES[machine_id]
    fault = machine["faults"][fault_id]

    baseline_rpm = machine["rated_rpm"]
    baseline_current = machine["rated_current_a"] * machine["typical_load_pct"]
    baseline_vib = machine["baseline_vibration_g"]
    baseline_temp = machine["baseline_temp_c"]
    voltage = 380.0

    injection_t = fault["injection_time_s"]
    data_points = []
    cumulative_energy_wh = 0.0
    cumulative_units = 0
    units_per_second = machine["production_rate_units_per_hour"] / 3600.0

    for t in range(duration_s):
        if t < injection_t:
            # Normal operation with small noise
            rpm = baseline_rpm + random.uniform(-5, 5)
            current = baseline_current + random.uniform(-1, 1)
            vib = baseline_vib + random.uniform(-0.01, 0.01)
            temp = baseline_temp + random.uniform(-0.3, 0.3)
            state = "RUNNING"
            alert = None
        else:
            # Fault progression
            fault_duration = t - injection_t
            progress = min(fault_duration / (duration_s - injection_t), 1.0)

            # Different fault signatures
            if fault_id == "mechanical_jam":
                rpm = max(0, baseline_rpm * (1 - progress * 1.2))
                current = baseline_current + (fault["current_spike_a"] - baseline_current) * min(progress * 1.5, 1.0)
                vib = baseline_vib * (1 + fault["vibration_increase_factor"] * progress * 2)
                temp = baseline_temp + fault["temp_increase_rate_c_per_min"] * (fault_duration / 60) * 15
            elif fault_id == "unbalance":
                rpm = baseline_rpm + random.uniform(-3, 3)
                current = baseline_current + random.uniform(-0.5, 0.5)
                vib = baseline_vib * (1 + fault["vibration_increase_factor"] * progress)
                temp = baseline_temp + random.uniform(-0.2, 0.2)
            elif fault_id == "thermal_overload":
                rpm = baseline_rpm * (1 - progress * 0.1)
                current = baseline_current * (1 + progress * 0.3)
                vib = baseline_vib * (1 + progress * 0.5)
                temp = baseline_temp + fault["temp_increase_rate_c_per_min"] * fault_duration
            elif fault_id == "voltage_sag":
                rpm = baseline_rpm * (1 - progress * 0.25)
                current = baseline_current * (1 + progress * 0.4)
                vib = baseline_vib * (1 + progress * 0.3)
                temp = baseline_temp + random.uniform(0, 2)
                voltage = 380 * (1 - progress * 0.15)
            elif fault_id == "overload":
                rpm = baseline_rpm * (1 - progress * 0.15)
                current = baseline_current + (fault["current_spike_a"] - baseline_current) * progress
                vib = baseline_vib * (1 + progress)
                temp = baseline_temp + fault["temp_increase_rate_c_per_min"] * fault_duration * 0.5
            elif fault_id == "loosening":
                rpm = baseline_rpm + random.uniform(-10, 10)
                current = baseline_current + random.uniform(-2, 2)
                vib = baseline_vib * (1 + fault["vibration_increase_factor"] * progress * 1.5)
                temp = baseline_temp + random.uniform(-0.5, 0.5)
            elif fault_id == "speed_droop":
                rpm = baseline_rpm * (1 - progress * 0.3)
                current = baseline_current * (1 + progress * 0.2)
                vib = baseline_vib * (1 + progress * 0.4)
                temp = baseline_temp + random.uniform(0, 1)

            # Determine state and alert
            if progress > 0.9 and fault_id in ["mechanical_jam", "thermal_overload"]:
                state = "FAULT"
                alert = f"🛑 {fault['name'].upper()}"
            elif progress > 0.7:
                state = "RUNNING"
                alert = "🔴 CRITICAL"
            elif progress > 0.4:
                state = "RUNNING"
                alert = "⚠⚠ High severity"
            elif progress > 0.1:
                state = "RUNNING"
                alert = "⚠ Anomaly detected"
            else:
                state = "RUNNING"
                alert = None

        # Calculate power and energy
        power_kw = (current * voltage * 0.85) / 1000.0
        energy_this_second = power_kw / 3600.0  # kWh per second
        cumulative_energy_wh += energy_this_second * 1000  # convert to Wh
        cumulative_units += units_per_second * (rpm / baseline_rpm)

        # OEE calculation
        availability = 1.0 if state == "RUNNING" else 0.0
        performance = rpm / baseline_rpm
        quality = 1.0 if abs(rpm - baseline_rpm) / baseline_rpm < 0.1 else 0.9
        oee = availability * performance * quality * 100

        data_points.append({
            "t_s": t,
            "rpm": round(max(0, rpm), 1),
            "current_a": round(max(0, current), 2),
            "voltage_v": round(voltage, 1),
            "power_kw": round(power_kw, 2),
            "temp_c": round(temp, 1),
            "vibration_g": round(max(0, vib), 3),
            "energy_wh": round(cumulative_energy_wh, 3),
            "units": int(cumulative_units),
            "oee_pct": round(max(0, min(100, oee)), 1),
            "state": state,
            "alert": alert
        })

    return {
        "scenario_id": f"{machine_id}_{fault_id}",
        "industry": machine["industry"],
        "equipment": machine["name"],
        "equipment_id": machine_id,
        "fault_type": fault["name"],
        "fault_id": fault_id,
        "duration_s": duration_s,
        "fault_injection_time_s": injection_t,
        "detection_time_with_pf_s": int(fault["time_to_detection_with_pf_min"] * 60),
        "detection_time_without_pf_s": int(fault["time_to_failure_without_pf_min"] * 60),
        "financial_constants": {
            "downtime_cost_egp_per_hour": machine["downtime_cost_egp_per_hour"],
            "energy_waste_cost_egp_per_minute": machine["energy_waste_cost_egp_per_min"],
            "scrap_cost_egp_per_unit": machine["scrap_cost_egp_per_unit"],
            "maintenance_repair_egp": fault["repair_cost_with_pf_egp"],
            "maintenance_replace_egp": fault["repair_cost_without_pf_egp"],
            "production_rate_units_per_hour": machine["production_rate_units_per_hour"]
        },
        "baseline": {
            "rated_rpm": baseline_rpm,
            "rated_current_a": machine["rated_current_a"],
            "typical_load_pct": machine["typical_load_pct"],
            "baseline_vibration_g": baseline_vib,
            "baseline_temp_c": baseline_temp,
            "voltage_v": voltage
        },
        "data_points": data_points
    }


def save_all_scenarios(output_dir: str = "simulation_data/scenarios"):
    """Generate and save all 9 scenarios."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    scenarios = [
        ("fertilizer_conveyor", "unbalance", 90),
        ("fertilizer_granulator", "mechanical_jam", 60),
        ("fertilizer_granulator", "thermal_overload", 120),
        ("fertilizer_mixer", "voltage_sag", 60),
        ("packaging_filling", "speed_droop", 90),
        ("packaging_filling", "mechanical_jam", 60),
        ("packaging_capping", "unbalance", 90),
        ("packaging_capping", "loosening", 90),
        ("packaging_labeling", "voltage_sag", 60),
    ]

    for machine_id, fault_id, duration in scenarios:
        if machine_id in MACHINE_PROFILES and fault_id in MACHINE_PROFILES[machine_id]["faults"]:
            scenario = generate_scenario(machine_id, fault_id, duration)
            filename = f"{machine_id}_{fault_id}.json"
            filepath = Path(output_dir) / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(scenario, f, indent=2, ensure_ascii=False)
            print(f"Generated {filename} ({len(scenario['data_points'])} points)")


if __name__ == "__main__":
    save_all_scenarios()
