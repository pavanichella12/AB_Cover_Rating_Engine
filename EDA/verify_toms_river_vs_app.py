"""
Verify Toms River dataset results against the app (Step 5) numbers.

Expected from your app screenshot (Replacement Cost = $132.30):
  - Per year: Staff, Total # of Absences, Total Replacement Cost
  - Overall: 1,293 staff, 90,158 absences, $11,927,908.10

Run from project root (with venv activated):

  source venv/bin/activate   # or: . venv\\Scripts\\activate on Windows
  python EDA/verify_toms_river_vs_app.py

Requires: raw_data/16503 - Toms River Absence History 7.1.20 to 6.30.25.xlsx
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "../raw_data")
FILE = "16503 - Toms River Absence History 7.1.20 to 6.30.25.xlsx"
PATH = os.path.join(RAW_DIR, FILE)

TEACHER_TYPES = ["Teacher", "ESY Teacher"]
# From your app screenshot (you may have entered 132.30 in Step 4)
REPLACEMENT_COST = 132.30

# Expected values from your app screenshot (for comparison)
EXPECTED = {
    "2020-2021": {"staff": 1069, "absences": 14683.786665333333, "replacement_cost": 1942664.98},
    "2021-2022": {"staff": 1060, "absences": 20450.606661066668, "replacement_cost": 2705615.26},
    "2022-2023": {"staff": 1078, "absences": 19445.619996133333, "replacement_cost": 2572655.53},
    "2023-2024": {"staff": 1067, "absences": 17619.5, "replacement_cost": 2331059.85},
    "2024-2025": {"staff": 1021, "absences": 17958.522222, "replacement_cost": 2375912.49},
    "overall": {"staff": 1293, "absences": 90158, "replacement_cost": 11927908.10},
    "5yr_avg_absences": 18031.6,
    "5yr_avg_staff": 1059.0,
    "5yr_avg_rc": 2385581.62,
}


def clean_toms_river(df: pd.DataFrame) -> pd.DataFrame:
    """Same cleaning as EDA/test_toms_river.py and the app."""
    df_clean = df.copy()
    df_clean = df_clean[~((df_clean["Filled"] == "Unfilled") & (df_clean["Needs Substitute"] == "NO"))]
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
        print("Put the Toms River Excel file in raw_data/ and re-run.")
        sys.exit(1)

    print("Loading Toms River dataset and applying same cleaning as app...")
    df = pd.read_excel(PATH)
    df_clean = clean_toms_river(df)
    n_years = df_clean["School Year"].dropna().nunique()
    school_years = sorted(df_clean["School Year"].dropna().unique().astype(str))

    print(f"Cleaned rows: {len(df_clean):,}")
    print(f"Replacement Cost Per Day: ${REPLACEMENT_COST:.2f}")
    print()

    # Per-school-year metrics (same formula as app)
    computed = {}
    for sy in school_years:
        sy_data = df_clean[df_clean["School Year"].astype(str) == sy]
        total_staff = int(sy_data["Employee Identifier"].nunique())
        total_absences = float(sy_data["Absence_Days"].sum())
        total_rc = total_absences * REPLACEMENT_COST
        computed[sy] = {"staff": total_staff, "absences": total_absences, "replacement_cost": total_rc}

    overall_staff = int(df_clean["Employee Identifier"].nunique())
    overall_absences = float(df_clean["Absence_Days"].sum())
    overall_rc = overall_absences * REPLACEMENT_COST
    computed["overall"] = {"staff": overall_staff, "absences": overall_absences, "replacement_cost": overall_rc}

    if n_years > 1:
        avg_staff = sum(computed[sy]["staff"] for sy in school_years) / n_years
        avg_absences = overall_absences / n_years
        avg_rc = avg_absences * REPLACEMENT_COST
        computed["5yr_avg"] = {"staff": avg_staff, "absences": avg_absences, "replacement_cost": avg_rc}

    # Compare to expected (from app screenshot)
    tol_staff = 0
    tol_absences = 0.01
    tol_rc = 1.0
    all_ok = True

    print("=" * 70)
    print("COMPARISON: Toms River dataset (this script) vs your app screenshot")
    print("=" * 70)

    for sy in school_years:
        if sy not in EXPECTED:
            continue
        exp = EXPECTED[sy]
        got = computed[sy]
        staff_ok = abs(got["staff"] - exp["staff"]) <= tol_staff
        abs_ok = abs(got["absences"] - exp["absences"]) <= tol_absences
        rc_ok = abs(got["replacement_cost"] - exp["replacement_cost"]) <= tol_rc
        row_ok = staff_ok and abs_ok and rc_ok
        if not row_ok:
            all_ok = False
        status = "OK" if row_ok else "MISMATCH"
        print(f"  {sy}: {status}")
        if not staff_ok:
            print(f"      Staff:     expected {exp['staff']}, got {got['staff']}")
        if not abs_ok:
            print(f"      Absences:  expected {exp['absences']:.2f}, got {got['absences']:.2f}")
        if not rc_ok:
            print(f"      Repl Cost: expected {exp['replacement_cost']:,.2f}, got {got['replacement_cost']:,.2f}")

    # Overall
    exp = EXPECTED["overall"]
    got = computed["overall"]
    staff_ok = abs(got["staff"] - exp["staff"]) <= tol_staff
    abs_ok = abs(got["absences"] - exp["absences"]) <= max(tol_absences, 1.0)
    rc_ok = abs(got["replacement_cost"] - exp["replacement_cost"]) <= max(tol_rc, 10.0)
    overall_ok = staff_ok and abs_ok and rc_ok
    if not overall_ok:
        all_ok = False
    status = "OK" if overall_ok else "MISMATCH"
    print(f"  Overall: {status}  (staff {got['staff']}, absences {got['absences']:,.2f}, replacement cost ${got['replacement_cost']:,.2f})")
    if not overall_ok:
        print(f"      Expected: staff {exp['staff']}, absences {exp['absences']}, replacement cost ${exp['replacement_cost']:,.2f}")

    print()
    if all_ok:
        print(">>> RESULTS MATCH: The app numbers are correct for the Toms River dataset.")
    else:
        print(">>> MISMATCH: Compare the values above. If the app used different filters or replacement cost, adjust EXPECTED in this script.")
    print("=" * 70)


if __name__ == "__main__":
    main()
