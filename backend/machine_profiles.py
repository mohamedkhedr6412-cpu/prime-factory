"""
PRIME-Factory v1.0 — Machine Profiles (MACHINE_PROFILES dictionary)
Source: Software Constitution v1.0, Section 5 — Dynamic Financial & Technical Modeling

All 6 machines across Fertilizer and Packaging industries with dynamic financial constants.
No hardcoded global constants — every machine and fault has its own profile.
"""

MACHINE_PROFILES = {
    "fertilizer_conveyor": {
        "id": "fertilizer_conveyor",
        "name": "Conveyor Belt Motor (7.5 kW)",
        "industry": "Fertilizer",
        "rated_power_kw": 7.5,
        "rated_rpm": 1450,
        "rated_current_a": 15.0,
        "typical_load_pct": 0.65,
        "baseline_vibration_g": 0.08,
        "baseline_temp_c": 45.0,

        # Financial constants (specific to conveyor)
        "downtime_cost_egp_per_hour": 5000.0,
        "energy_waste_cost_egp_per_min": 15.0,
        "scrap_cost_egp_per_unit": 15.0,
        "production_rate_units_per_hour": 1200.0,

        "faults": {
            "unbalance": {
                "name": "Severe Unbalance (Material Buildup)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 240.0,  # 4 hours
                "time_to_detection_with_pf_min": 5.0,     # 5 minutes
                "repair_cost_without_pf_egp": 15000.0,    # Shaft replacement
                "repair_cost_with_pf_egp": 300.0,         # Rebalancing
                "units_lost_per_minute": 1200.0 / 60,     # 20 units/min
                "current_spike_a": 18.0,
                "vibration_increase_factor": 3.5,
                "temp_increase_rate_c_per_min": 0.5
            },
            "loosening": {
                "name": "Bolt Loosening (Vibration Fatigue)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 480.0,  # 8 hours
                "time_to_detection_with_pf_min": 15.0,
                "repair_cost_without_pf_egp": 8000.0,
                "repair_cost_with_pf_egp": 150.0,
                "units_lost_per_minute": 1200.0 / 60,
                "current_spike_a": 16.0,
                "vibration_increase_factor": 2.0,
                "temp_increase_rate_c_per_min": 0.3
            }
        }
    },

    "fertilizer_granulator": {
        "id": "fertilizer_granulator",
        "name": "Granulator Drum Motor (45 kW)",
        "industry": "Fertilizer",
        "rated_power_kw": 45.0,
        "rated_rpm": 980,
        "rated_current_a": 85.0,
        "typical_load_pct": 0.80,
        "baseline_vibration_g": 0.12,
        "baseline_temp_c": 55.0,

        # Financial constants (specific to granulator)
        "downtime_cost_egp_per_hour": 8000.0,
        "energy_waste_cost_egp_per_min": 25.0,
        "scrap_cost_egp_per_unit": 50.0,
        "production_rate_units_per_hour": 20000.0,  # kg/hour equivalent

        "faults": {
            "mechanical_jam": {
                "name": "Mechanical Jam (Wet Clumps)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 45.0,
                "time_to_detection_with_pf_min": 0.25,  # 15 seconds
                "repair_cost_without_pf_egp": 35000.0,  # Full motor/gearbox
                "repair_cost_with_pf_egp": 800.0,       # Clearing + bearing check
                "units_lost_per_minute": 20000.0 / 60,
                "current_spike_a": 180.0,
                "vibration_increase_factor": 8.0,
                "temp_increase_rate_c_per_min": 3.0
            },
            "thermal_overload": {
                "name": "Thermal Overload (Cooling Blockage)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 120.0,
                "time_to_detection_with_pf_min": 10.0,
                "repair_cost_without_pf_egp": 25000.0,
                "repair_cost_with_pf_egp": 500.0,
                "units_lost_per_minute": 20000.0 / 60,
                "current_spike_a": 95.0,
                "vibration_increase_factor": 1.5,
                "temp_increase_rate_c_per_min": 4.0
            }
        }
    },

    "fertilizer_mixer": {
        "id": "fertilizer_mixer",
        "name": "Mixer Motor (11 kW)",
        "industry": "Fertilizer",
        "rated_power_kw": 11.0,
        "rated_rpm": 1440,
        "rated_current_a": 22.0,
        "typical_load_pct": 0.60,
        "baseline_vibration_g": 0.06,
        "baseline_temp_c": 40.0,

        # Financial constants (specific to mixer)
        "downtime_cost_egp_per_hour": 4000.0,
        "energy_waste_cost_egp_per_min": 12.0,
        "scrap_cost_egp_per_unit": 20.0,
        "production_rate_units_per_hour": 5000.0,

        "faults": {
            "unbalance": {
                "name": "Uneven Load Distribution",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 180.0,
                "time_to_detection_with_pf_min": 8.0,
                "repair_cost_without_pf_egp": 12000.0,
                "repair_cost_with_pf_egp": 250.0,
                "units_lost_per_minute": 5000.0 / 60,
                "current_spike_a": 28.0,
                "vibration_increase_factor": 4.0,
                "temp_increase_rate_c_per_min": 1.5
            },
            "voltage_sag": {
                "name": "Voltage Sag (Grid Fluctuation)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 60.0,
                "time_to_detection_with_pf_min": 2.0,
                "repair_cost_without_pf_egp": 5000.0,
                "repair_cost_with_pf_egp": 100.0,
                "units_lost_per_minute": 5000.0 / 60,
                "current_spike_a": 30.0,
                "vibration_increase_factor": 1.2,
                "temp_increase_rate_c_per_min": 2.0
            }
        }
    },

    "packaging_filling": {
        "id": "packaging_filling",
        "name": "Filling Machine Motor (2.2 kW)",
        "industry": "Packaging",
        "rated_power_kw": 2.2,
        "rated_rpm": 2850,
        "rated_current_a": 4.5,
        "typical_load_pct": 0.50,
        "baseline_vibration_g": 0.04,
        "baseline_temp_c": 38.0,

        "downtime_cost_egp_per_hour": 2000.0,
        "energy_waste_cost_egp_per_min": 8.0,
        "scrap_cost_egp_per_unit": 5.0,
        "production_rate_units_per_hour": 3600.0,

        "faults": {
            "speed_droop": {
                "name": "Speed Droop (Belt Wear)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 360.0,
                "time_to_detection_with_pf_min": 10.0,
                "repair_cost_without_pf_egp": 3000.0,
                "repair_cost_with_pf_egp": 200.0,
                "units_lost_per_minute": 3600.0 / 60,
                "current_spike_a": 6.0,
                "vibration_increase_factor": 1.5,
                "temp_increase_rate_c_per_min": 1.0
            },
            "mechanical_jam": {
                "name": "Mechanical Jam (Bottle Blockage)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 30.0,
                "time_to_detection_with_pf_min": 0.25,
                "repair_cost_without_pf_egp": 8000.0,
                "repair_cost_with_pf_egp": 300.0,
                "units_lost_per_minute": 3600.0 / 60,
                "current_spike_a": 12.0,
                "vibration_increase_factor": 5.0,
                "temp_increase_rate_c_per_min": 2.5
            }
        }
    },

    "packaging_capping": {
        "id": "packaging_capping",
        "name": "Capping Machine Motor (1.5 kW)",
        "industry": "Packaging",
        "rated_power_kw": 1.5,
        "rated_rpm": 1440,
        "rated_current_a": 3.2,
        "typical_load_pct": 0.40,
        "baseline_vibration_g": 0.03,
        "baseline_temp_c": 35.0,

        "downtime_cost_egp_per_hour": 1800.0,
        "energy_waste_cost_egp_per_min": 6.0,
        "scrap_cost_egp_per_unit": 3.0,
        "production_rate_units_per_hour": 4200.0,

        "faults": {
            "unbalance": {
                "name": "Spindle Unbalance",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 200.0,
                "time_to_detection_with_pf_min": 5.0,
                "repair_cost_without_pf_egp": 4000.0,
                "repair_cost_with_pf_egp": 150.0,
                "units_lost_per_minute": 4200.0 / 60,
                "current_spike_a": 5.0,
                "vibration_increase_factor": 3.0,
                "temp_increase_rate_c_per_min": 0.8
            },
            "loosening": {
                "name": "Fastener Loosening",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 400.0,
                "time_to_detection_with_pf_min": 12.0,
                "repair_cost_without_pf_egp": 2500.0,
                "repair_cost_with_pf_egp": 100.0,
                "units_lost_per_minute": 4200.0 / 60,
                "current_spike_a": 4.0,
                "vibration_increase_factor": 2.5,
                "temp_increase_rate_c_per_min": 0.5
            }
        }
    },

    "packaging_labeling": {
        "id": "packaging_labeling",
        "name": "Labeling Machine Motor (0.75 kW)",
        "industry": "Packaging",
        "rated_power_kw": 0.75,
        "rated_rpm": 2850,
        "rated_current_a": 1.8,
        "typical_load_pct": 0.30,
        "baseline_vibration_g": 0.02,
        "baseline_temp_c": 32.0,

        "downtime_cost_egp_per_hour": 1500.0,
        "energy_waste_cost_egp_per_min": 5.0,
        "scrap_cost_egp_per_unit": 2.0,
        "production_rate_units_per_hour": 4800.0,

        "faults": {
            "voltage_sag": {
                "name": "Voltage Sag (Grid Fluctuation)",
                "injection_time_s": 10,
                "time_to_failure_without_pf_min": 90.0,
                "time_to_detection_with_pf_min": 3.0,
                "repair_cost_without_pf_egp": 2000.0,
                "repair_cost_with_pf_egp": 80.0,
                "units_lost_per_minute": 4800.0 / 60,
                "current_spike_a": 3.0,
                "vibration_increase_factor": 1.3,
                "temp_increase_rate_c_per_min": 1.2
            }
        }
    }
}
