#!/usr/bin/env python3
"""Simulate data retrieval from Sigenergy API to show AC run status and related fields."""

import json
from tests.conftest import SAMPLE_ENERGY_FLOW, SAMPLE_ALL_DATA

def display_energy_flow_data():
    """Display energy flow data including AC run status."""
    print("=" * 70)
    print("SIMULATED ENERGY FLOW DATA RETRIEVAL FROM SIGENERGY API")
    print("=" * 70)
    print("\nEnergy Flow Data (includes AC run status):")
    print(json.dumps(SAMPLE_ENERGY_FLOW, indent=2))
    
    print("\n" + "=" * 70)
    print("EXTRACTED & FORMATTED ENTITY VALUES")
    print("=" * 70)
    
    # Show key extracted fields
    fields = [
        ("AC Run Status", SAMPLE_ENERGY_FLOW.get("acRunStatus")),
        ("AC Power", SAMPLE_ENERGY_FLOW.get("acPower")),
        ("PV Power", SAMPLE_ENERGY_FLOW.get("pvPower")),
        ("Battery Power", SAMPLE_ENERGY_FLOW.get("batteryPower")),
        ("Battery SoC", SAMPLE_ENERGY_FLOW.get("batterySoc")),
        ("Load Power", SAMPLE_ENERGY_FLOW.get("loadPower")),
        ("Grid Power (Buy/Sell)", SAMPLE_ENERGY_FLOW.get("buySellPower")),
        ("Online Status", SAMPLE_ENERGY_FLOW.get("online")),
    ]
    
    print("\nEnergy Flow Sensor Values:")
    for label, value in fields:
        print(f"  {label:<30} : {value}")
    
    print("\n" + "=" * 70)
    print("COMPLETE COORDINATOR DATA")
    print("=" * 70)
    print(json.dumps({k: v for k, v in SAMPLE_ALL_DATA.items() 
                      if k in ["energy_flow", "current_mode", "weather"]}, 
                     indent=2, default=str))

if __name__ == "__main__":
    display_energy_flow_data()
