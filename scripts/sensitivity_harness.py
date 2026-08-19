import os
import sys
import json
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from store.db import get_session_factory
from store.repo import get_settings, save_settings
from store.models import ScoreRow, TelemetryRow
from contract.settings import Settings

def dry_run_historical_scores(session, proposed_settings):
    print("\n--- Dry Run: Historical Impact Analysis ---")
    scores = session.scalars(select(ScoreRow)).all()
    if not scores:
        print("No historical scores found to dry-run against.")
        return
        
    original_failures = 0
    new_failures = 0
    total = len(scores)
    
    for row in scores:
        metrics = row.metrics or {}
        r_score = metrics.get('R', 1.0)
        
        # Check old gating logic (was hardcoded to < 0.70)
        # Check new gating logic (against proposed_settings.gate_thresholds['R'])
        
        if r_score < 0.70:
            original_failures += 1
            
        if r_score < proposed_settings.gate_thresholds.get('R', 0.70):
            new_failures += 1
            
    print(f"Total historical runs evaluated: {total}")
    print(f"Original Gate Failures (R < 0.70): {original_failures} ({(original_failures/total)*100:.1f}%)")
    print(f"Proposed Gate Failures (R < {proposed_settings.gate_thresholds.get('R', 0.70)}): {new_failures} ({(new_failures/total)*100:.1f}%)")
    print(f"Net Change in Blocked Runs: {new_failures - original_failures}")


def main():
    print("=== DPI-LS Sensitivity Harness ===")
    
    try:
        r_max = float(input("Enter proposed r_max (e.g. 10.0): "))
        gate_r = float(input("Enter proposed Risk Gate Threshold (e.g. 0.70): "))
        q_acc = float(input("Enter Q_sub_weight for accuracy (e.g. 0.70): "))
        q_con = float(input("Enter Q_sub_weight for consistency (e.g. 0.20): "))
        q_hal = float(input("Enter Q_sub_weight for hallucination (e.g. 0.10): "))
    except ValueError:
        print("Invalid input. Aborting.")
        sys.exit(1)
        
    proposed = Settings(
        r_max=r_max,
        gate_thresholds={"G": 0.60, "R": gate_r, "V": 0.60},
        q_sub_weights={"accuracy": q_acc, "consistency": q_con, "hallucination": q_hal}
    )
    
    with get_session_factory()() as session:
        dry_run_historical_scores(session, proposed)
        
        commit = input("\nCommit these calibration constants to the database? (y/n): ")
        if commit.lower() == 'y':
            save_settings(session, proposed)
            session.commit()
            print("Successfully updated app_settings in database.")
        else:
            print("Aborted. Database unchanged.")

if __name__ == '__main__':
    main()
