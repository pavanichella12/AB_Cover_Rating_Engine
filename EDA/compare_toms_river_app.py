"""
Compare EDA test_toms_river.py cleaning result (99,120 rows) with app pipeline.
Run from project root: python EDA/compare_toms_river_app.py

Use this to verify the app produces the same "After Cleaning" count as the EDA.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "../raw_data")
FILE = "16503 - Toms River Absence History 7.1.20 to 6.30.25.xlsx"
PATH = os.path.join(RAW_DIR, FILE)

TEACHER_TYPES = ["Teacher", "ESY Teacher"]
EXPECTED_FINAL_ROWS = 99_120


def run_eda_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """Same logic as EDA/test_toms_river.py ."""
    df_clean = df.copy()
    # Rule 1
    df_clean = df_clean[~((df_clean["Filled"] == "Unfilled") & (df_clean["Needs Substitute"] == "NO"))]
    # Rule 2
    df_clean = df_clean[df_clean["Employee Type"].isin(TEACHER_TYPES)]

    def date_in_school_year(row):
        sy = str(row["School Year"]).split("-")
        if len(sy) != 2:
            return True
        start_year, end_year = int(sy[0]), int(sy[1])
        start = pd.Timestamp(year=start_year, month=7, day=1)
        end = pd.Timestamp(year=end_year, month=6, day=30)
        dt = pd.to_datetime(row["Date"])
        return start <= dt <= end

    df_clean["Date"] = pd.to_datetime(df_clean["Date"], errors="coerce")
    df_clean = df_clean[df_clean.apply(date_in_school_year, axis=1)]

    def calc_absence_days(row):
        t = str(row.get("Absence Type", "")).strip()
        if t == "Full Day":
            return 1.0
        if t in ["AM Half Day", "PM Half Day"]:
            return 0.5
        if t == "Custom Duration":
            h = pd.to_numeric(row.get("Duration", 0), errors="coerce")
            return (h / 7.5) if pd.notna(h) else 0
        return 0

    df_clean["Absence_Days"] = df_clean.apply(calc_absence_days, axis=1)
    return df_clean


def main():
    if not os.path.isfile(PATH):
        print(f"File not found: {PATH}")
        print("Upload the Toms River file to raw_data/ and re-run.")
        sys.exit(1)

    print("=" * 60)
    print("Toms River: EDA vs App cleaning")
    print("=" * 60)

    df_raw = pd.read_excel(PATH)
    print(f"\nRaw rows: {len(df_raw):,}")

    # EDA pipeline (source of truth)
    df_eda = run_eda_cleaning(df_raw)
    eda_rows = len(df_eda)
    print(f"EDA (test_toms_river) After Cleaning: {eda_rows:,} (expected {EXPECTED_FINAL_ROWS:,})")

    # App pipeline: select (filter Teacher + ESY) then clean
    from agents.data_cleaning_agent_llm import DataCleaningAgentLLM

    # Simulate Step 2: user filtered to Teacher, ESY Teacher
    df_selected = df_raw[df_raw["Employee Type"].isin(TEACHER_TYPES)].copy()
    print(f"App selected_data (Teacher + ESY only): {len(df_selected):,}")

    blackboard = {
        "user_selected_employee_types": TEACHER_TYPES,
        "user_already_filtered_employee_types": True,
    }
    cleaning_agent = DataCleaningAgentLLM()
    df_app, stats = cleaning_agent.process(df_selected, school_name="tomsriver", blackboard_context=blackboard)
    app_rows = len(df_app)
    print(f"App After Cleaning: {app_rows:,}")

    # Step-by-step from stats
    if stats.get("after_validation") is not None:
        print(f"  after_validation: {stats['after_validation']:,}")
    print(f"  after_rule1: {stats.get('after_rule1', 0):,}")
    print(f"  after_rule2: {stats.get('after_rule2', 0):,}")
    print(f"  after_rule3: {stats.get('after_rule3', 0):,}")

    print("\n" + "=" * 60)
    if app_rows == EXPECTED_FINAL_ROWS and eda_rows == EXPECTED_FINAL_ROWS:
        print("PASS: App and EDA both give 99,120 rows after cleaning.")
    elif app_rows != eda_rows:
        print(f"MISMATCH: EDA={eda_rows:,} vs App={app_rows:,} (diff={app_rows - eda_rows:+,})")
        if stats.get("validation_report"):
            vr = stats["validation_report"]
            print(f"  Validation report rows_removed: {vr.get('rows_removed', 0)}")
        sys.exit(1)
    else:
        print("PASS: App matches EDA row count.")
    print("=" * 60)


if __name__ == "__main__":
    main()
