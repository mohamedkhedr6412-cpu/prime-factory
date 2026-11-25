"""
PRIME-Factory v1.0 — Financial Calculator (Dynamic)
Source: Software Constitution v1.0, Section 12 — Financial Calculator (Dynamic)

Calculates dynamic financial losses based on machine profile and fault.
NO hardcoded global constants.
"""

from backend.machine_profiles import MACHINE_PROFILES


class FinancialCalculator:
    """
    Calculates dynamic financial losses based on machine profile and fault.
    NO hardcoded global constants.
    """

    @staticmethod
    def calculate_without_pf(machine_id: str, fault_id: str) -> dict:
        """Calculate losses WITHOUT PRIME-Factory (catastrophic failure)."""
        machine = MACHINE_PROFILES[machine_id]
        fault = machine["faults"][fault_id]

        downtime_min = fault["time_to_failure_without_pf_min"]
        downtime_hours = downtime_min / 60

        downtime_cost = downtime_hours * machine["downtime_cost_egp_per_hour"]
        energy_waste = downtime_min * machine["energy_waste_cost_egp_per_min"]
        scrap_cost = fault["units_lost_per_minute"] * downtime_min * machine["scrap_cost_egp_per_unit"]
        repair_cost = fault["repair_cost_without_pf_egp"]

        total_loss = downtime_cost + energy_waste + scrap_cost + repair_cost

        return {
            "detection_time_min": downtime_min,
            "downtime_min": downtime_min,
            "downtime_cost_egp": round(downtime_cost, 2),
            "energy_waste_egp": round(energy_waste, 2),
            "scrap_cost_egp": round(scrap_cost, 2),
            "repair_cost_egp": round(repair_cost, 2),
            "total_loss_egp": round(total_loss, 2)
        }

    @staticmethod
    def calculate_with_pf(machine_id: str, fault_id: str) -> dict:
        """Calculate losses WITH PRIME-Factory (early detection)."""
        machine = MACHINE_PROFILES[machine_id]
        fault = machine["faults"][fault_id]

        detection_min = fault["time_to_detection_with_pf_min"]
        # Planned maintenance downtime: dynamic, never longer than the
        # catastrophic failure it prevents (avoids negative savings).
        planned_downtime_min = min(
            120,
            max(30, fault["time_to_failure_without_pf_min"] * 0.5),
        )
        # Guarantee a strictly shorter stop than the failure itself
        # (e.g. packaging_filling/mechanical_jam: 30 min failure vs 30 min stop).
        planned_downtime_min = min(
            planned_downtime_min,
            max(1, fault["time_to_failure_without_pf_min"] - 1),
        )

        downtime_cost = (planned_downtime_min / 60) * machine["downtime_cost_egp_per_hour"]
        energy_waste = detection_min * machine["energy_waste_cost_egp_per_min"]
        scrap_cost = fault["units_lost_per_minute"] * detection_min * machine["scrap_cost_egp_per_unit"]
        repair_cost = fault["repair_cost_with_pf_egp"]

        total_loss = downtime_cost + energy_waste + scrap_cost + repair_cost

        return {
            "detection_time_min": detection_min,
            "downtime_min": planned_downtime_min,
            "downtime_cost_egp": round(downtime_cost, 2),
            "energy_waste_egp": round(energy_waste, 2),
            "scrap_cost_egp": round(scrap_cost, 2),
            "repair_cost_egp": round(repair_cost, 2),
            "total_loss_egp": round(total_loss, 2)
        }

    @staticmethod
    def calculate_savings(machine_id: str, fault_id: str) -> dict:
        """Calculate total savings."""
        without = FinancialCalculator.calculate_without_pf(machine_id, fault_id)
        with_pf = FinancialCalculator.calculate_with_pf(machine_id, fault_id)

        total_savings = without["total_loss_egp"] - with_pf["total_loss_egp"]
        savings_pct = (total_savings / without["total_loss_egp"]) * 100 if without["total_loss_egp"] > 0 else 0

        downtime_reduction = (
            (without["downtime_min"] - with_pf["downtime_min"]) / without["downtime_min"]
        ) * 100

        machine = MACHINE_PROFILES[machine_id]
        fault = machine["faults"][fault_id]
        units_saved = int(
            fault["units_lost_per_minute"] * (without["downtime_min"] - with_pf["downtime_min"])
        )

        return {
            "without_pf": without,
            "with_pf": with_pf,
            "total_savings_egp": round(total_savings, 2),
            "savings_pct": round(savings_pct, 1),
            "downtime_reduction_pct": round(downtime_reduction, 1),
            "units_saved": units_saved
        }
