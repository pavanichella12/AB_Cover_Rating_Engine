"""
Verify Woodbridge dataset results against the app (Step 5) numbers.

Expected from your app screenshot (Replacement Cost = $167.00):
  - Overall: 1,406 staff, 106,280.00 absences, $17,748,765.19

Run from project root: python EDA/verify_woodbridge_vs_app.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "../raw_data")
FILE = "18559 - Woodbridge Absence History 7.1.20 to 6.30.25.xlsx"
PATH = os.path.join(RAW_DIR, FILE)

REPLACEMENT_COST = 167.00

EXPECTED = {
    "2020-2021": {"staff": 651, "absences": 9394.12, "replacement_cost": 1568818.41},
    "2021-2022": {"staff": 1125, "absences": 24882.42, "replacement_cost": 4155364.51},
    "2022-2023": {"staff": 1136, "absences": 24536.11, "replacement_cost": 4097530.93},
    "2023-2024": {"staff": 1165, "absences": 24282.81, "replacement_cost": 4055229.08},
    "2024-2025": {"staff": 1073, "absences": 23184.56, "replacement_cost": 3871822.26},
    "overall": {"staff": 1406, "absences": 106280.00, "replacement_cost": 17748765.19},
}


def clean_df(df: pd.DataFrame, employee_types_to_keep=None) -> pd.DataFrame:
    """Same cleaning as app: Rule 1, Rule 2 (optional), Rule 3, Absence_Days."""
    df_clean = df.copy()
    df_clean = df_clean[~((df_clean["Filled"] == "Unfilled") & (df_clean["Needs Substitute"] == "NO"))]
    if employee_types_to_keep is not None:
        df_clean = df_clean[df_clean["Employee Type"].isin(employee_types_to_keep)]

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


def compute_metrics(df_clean: pd.DataFrame):
    school_years = sorted(df_clean["School Year"].dropna().unique().astype(str))
    computed = {}
    for sy in school_years:
        sy_data = df_clean[df_clean["School Year"].astype(str) == sy]
        computed[sy] = {
            "staff": int(sy_data["Employee Identifier"].nunique()),
            "absences": float(sy_data["Absence_Days"].sum()),
            "replacement_cost": float(sy_data["Absence_Days"].sum()) * REPLACEMENT_COST,
        }
    overall_absences = float(df_clean["Absence_Days"].sum())
    computed["overall"] = {
        "staff": int(df_clean["Employee Identifier"].nunique()),
        "absences": overall_absences,
        "replacement_cost": overall_absences * REPLACEMENT_COST,
    }
    return computed, school_years


def main():
    if not os.path.isfile(PATH):
        print(f"File not found: {PATH}")
        sys.exit(1)

    print("Loading Woodbridge dataset...")
    df = pd.read_excel(PATH)
    print(f"Raw rows: {len(df):,}")
    if "Employee Type" in df.columns:
        print(f"Employee types: {df['Employee Type'].unique().tolist()}")
    print()

    # Try different employee type filters to match app
    candidates = [
        (None, "All employee types"),
        (["Teacher", "ESY Teacher"], "Teacher, ESY Teacher"),
        (["Teacher"], "Teacher only"),
    ]
    if "Employee Type" in df.columns:
        ut = df["Employee Type"].dropna().unique().tolist()
        teacher_like = [t for t in ut if "teacher" in str(t).lower() or "Teacher" in str(t)]
        if teacher_like and teacher_like not in [c[0] for c in candidates if c[0]]:
            candidates.append((teacher_like, f"Teacher-like: {teacher_like}"))

    match_computed = None
    match_label = None
    tol_abs, tol_rc = 1.0, 10.0

    for employee_types, label in candidates:
        df_clean = clean_df(df, employee_types_to_keep=employee_types)
        computed, school_years = compute_metrics(df_clean)
        g = computed["overall"]
        e = EXPECTED["overall"]
        if g["staff"] != e["staff"]:
            continue
        if abs(g["absences"] - e["absences"]) > tol_abs or abs(g["replacement_cost"] - e["replacement_cost"]) > tol_rc:
            continue
        # Check per-year
        all_ok = True
        for sy in school_years:
            if sy not in EXPECTED:
                continue
            ge, ex = computed[sy], EXPECTED[sy]
            if abs(ge["absences"] - ex["absences"]) > tol_abs or abs(ge["replacement_cost"] - ex["replacement_cost"]) > tol_rc:
                all_ok = False
                break
        if all_ok:
            match_computed = computed
            match_label = label
            break

    if match_computed is None:
        # Use no filter and show comparison anyway
        df_clean = clean_df(df, employee_types_to_keep=None)
        match_computed, school_years = compute_metrics(df_clean)
        match_label = "All employee types"

    print("=" * 70)
    print("COMPARISON: Woodbridge dataset vs your app screenshot")
    print("=" * 70)
    print(f"Replacement Cost Per Day: ${REPLACEMENT_COST:.2f}")
    print(f"Filter used: {match_label}")
    print()

    computed = match_computed
    all_ok = True
    for sy in sorted(computed.keys()):
        if sy == "overall":
            continue
        g = computed[sy]
        e = EXPECTED.get(sy)
        if not e:
            continue
        ok = g["staff"] == e["staff"] and abs(g["absences"] - e["absences"]) <= tol_abs and abs(g["replacement_cost"] - e["replacement_cost"]) <= tol_rc
        if not ok:
            all_ok = False
        status = "OK" if ok else "MISMATCH"
        print(f"  {sy}: {status}  staff={g['staff']}, absences={g['absences']:,.2f}, replacement cost=${g['replacement_cost']:,.2f}")

    g = computed["overall"]
    e = EXPECTED["overall"]
    ok_overall = g["staff"] == e["staff"] and abs(g["absences"] - e["absences"]) <= tol_abs and abs(g["replacement_cost"] - e["replacement_cost"]) <= tol_rc
    if not ok_overall:
        all_ok = False
    status = "OK" if ok_overall else "MISMATCH"
    print(f"  Overall: {status}  staff={g['staff']}, absences={g['absences']:,.2f}, replacement cost=${g['replacement_cost']:,.2f}")

    print()
    if all_ok:
        print(">>> RESULTS MATCH: The app numbers are correct for Woodbridge.")
    else:
        print(">>> MISMATCH: If you applied employee type filters in Step 2, set them in this script and re-run.")
    print("=" * 70)


if __name__ == "__main__":
    main()
