"""
PRIME-Factory v1.0 — Comparison Engine
Source: Software Constitution v1.0, Section 14 — Comparison Engine

Generates final comparison report after both timelines complete.
"""

from typing import List, Dict
from backend.machine_profiles import MACHINE_PROFILES
from backend.financial_calculator import FinancialCalculator


class ComparisonEngine:
    """
    Generates final comparison report after both timelines complete.
    """

    @staticmethod
    def generate_report(
        machine_id: str,
        fault_id: str,
        without_data: List[Dict],
        with_data: List[Dict]
    ) -> dict:
        """Generate comprehensive comparison report."""
        savings = FinancialCalculator.calculate_savings(machine_id, fault_id)
        machine = MACHINE_PROFILES[machine_id]
        fault = machine["faults"][fault_id]

        return {
            "scenario": {
                "machine": machine["name"],
                "fault": fault["name"],
                "industry": machine["industry"]
            },
            "financial_comparison": {
                "without_pf": savings["without_pf"],
                "with_pf": savings["with_pf"],
                "total_savings_egp": savings["total_savings_egp"],
                "savings_pct": savings["savings_pct"]
            },
            "technical_comparison": {
                "downtime_reduction_pct": savings["downtime_reduction_pct"],
                "units_saved": savings["units_saved"],
                "detection_time_without_pf_min": savings["without_pf"]["detection_time_min"],
                "detection_time_with_pf_min": savings["with_pf"]["detection_time_min"]
            },
            "data_summary": {
                "without_pf_points": len(without_data),
                "with_pf_points": len(with_data),
                "without_pf_final_state": without_data[-1]["state"] if without_data else "N/A",
                "with_pf_final_state": with_data[-1]["state"] if with_data else "N/A"
            }
        }
