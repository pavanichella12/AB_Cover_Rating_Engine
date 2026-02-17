"""
Test script for Toms River - same logic as test.ipynb and app.
Run: python EDA/test_toms_river.py
Compare with app results after uploading Toms River file.
"""

import os
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "../raw_data")
FILE = "16503 - Toms River Absence History 7.1.20 to 6.30.25.xlsx"

DEDUCTIBLE = 20
CC_DAYS = 60
REPLACEMENT_COST = 150.0
ARK_RATE = 0.15
ABCOVER_RATE = 0.15
SCHOOL_YEAR_DAYS = 180
CC_MAX = DEDUCTIBLE + CC_DAYS
TEACHER_TYPES = ["Teacher", "ESY Teacher"]

path = os.path.join(RAW_DIR, FILE)
if not os.path.isfile(path):
    print(f"File not found: {path}")
    exit(1)

df = pd.read_excel(path)
print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")
print()
print("Column names:", list(df.columns))
print()
if "Employee Type" in df.columns:
    print(f"Employee Type - unique values: {df['Employee Type'].nunique()}")
    print(df["Employee Type"].unique())
print()

# Cleaning rules
df_clean = df.copy()
df_clean = df_clean[~((df_clean["Filled"] == "Unfilled") & (df_clean["Needs Substitute"] == "NO"))]
print(f"After Rule 1 (Unfilled+NO): {len(df_clean)}")
df_clean = df_clean[df_clean["Employee Type"].isin(TEACHER_TYPES)]
print(f"After Rule 2 (Employee Type): {len(df_clean)}")


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
print(f"After Rule 3 (School Year dates): {len(df_clean)}")


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
print(f"Final rows: {len(df_clean)}")
print()

# Premium calculation
teacher_days = df_clean.groupby("Employee Identifier")["Absence_Days"].sum().reset_index()
teacher_days.columns = ["Employee Identifier", "Total_Days"]
total_days_per_teacher = teacher_days.set_index("Employee Identifier")["Total_Days"]

staff_cc = total_days_per_teacher[
    (total_days_per_teacher > DEDUCTIBLE) & (total_days_per_teacher <= CC_MAX)
]
total_cc_days = sum(min(d - DEDUCTIBLE, CC_MAX - DEDUCTIBLE) for d in staff_cc)

staff_high = total_days_per_teacher[total_days_per_teacher > CC_MAX]
excess_days = (staff_high - CC_MAX).sum()

replacement_cost_cc = REPLACEMENT_COST * total_cc_days
ark_commission = replacement_cost_cc * ARK_RATE
abcover_commission = replacement_cost_cc * ABCOVER_RATE
total_premium = replacement_cost_cc + ark_commission + abcover_commission

print(f"Teachers: {len(teacher_days)} | In CC range: {len(staff_cc)} | High claimants: {len(staff_high)}")
print(f"Total CC Days: {total_cc_days:.2f} | Excess Days: {excess_days:.2f}")
print(f"Replacement (CC): ${replacement_cost_cc:,.2f} | ARK: ${ark_commission:,.2f} | ABCover: ${abcover_commission:,.2f}")
print(f"TOTAL PREMIUM: ${total_premium:,.2f}")
print()

# School Year Metrics table
table_data = []
for sy in sorted(df_clean["School Year"].dropna().unique()):
    sy_data = df_clean[df_clean["School Year"] == sy]
    total_staff = sy_data["Employee Identifier"].nunique()
    total_absences = sy_data["Absence_Days"].sum()
    total_rc = total_absences * REPLACEMENT_COST
    table_data.append({
        "School Year": sy,
        "Total # Of Staff": total_staff,
        "Total # of Absences": f"{total_absences:,.2f}",
        "Replacement Cost Per Day ($)": f"${REPLACEMENT_COST:.2f}",
        "Total Replacement Cost to District ($)": f"${total_rc:,.2f}",
        "Amt. of School Year Days": SCHOOL_YEAR_DAYS,
        "Waiting Period 'Deductible' (Days)": DEDUCTIBLE,
        "'CC' Maximum Days (per staff member)": CC_DAYS,
    })
n = len(table_data)
if n > 1:
    avg_staff = sum(df_clean.groupby("School Year")["Employee Identifier"].nunique()) / n
    avg_absences = df_clean["Absence_Days"].sum() / n
    avg_rc = avg_absences * REPLACEMENT_COST
    table_data.append({
        "School Year": "5-Yr Avg",
        "Total # Of Staff": f"{avg_staff:.1f}",
        "Total # of Absences": f"{avg_absences:,.1f}",
        "Replacement Cost Per Day ($)": f"${REPLACEMENT_COST:.2f}",
        "Total Replacement Cost to District ($)": f"${avg_rc:,.2f}",
        "Amt. of School Year Days": SCHOOL_YEAR_DAYS,
        "Waiting Period 'Deductible' (Days)": DEDUCTIBLE,
        "'CC' Maximum Days (per staff member)": CC_DAYS,
    })
print("School Year Metrics (same as app):")
print(pd.DataFrame(table_data).to_string(index=False))
print()

# Calculation Breakdown
below_deductible = (total_days_per_teacher <= DEDUCTIBLE).sum()
high_claimant_cost = REPLACEMENT_COST * excess_days
print("=" * 60)
print("CALCULATION BREAKDOWN")
print("=" * 60)
print()
print("1. Base (Replacement Cost × CC Days)")
print(f"   ${REPLACEMENT_COST:,.2f} × {total_cc_days:,.2f} = ${replacement_cost_cc:,.2f}")
print()
print("2. ARK Commission")
print(f"   Base × {ARK_RATE*100:.0f}% = ${ark_commission:,.2f}")
print()
print("3. ABCover Commission")
print(f"   Base × {ABCOVER_RATE*100:.0f}% = ${abcover_commission:,.2f}")
print()
print("4. Total Premium")
print(f"   ${replacement_cost_cc:,.2f} + ${ark_commission:,.2f} + ${abcover_commission:,.2f} = ${total_premium:,.2f}")
print()
print("Teacher Distribution:")
print(f"  Total: {len(teacher_days):,} | Below Deductible: {below_deductible:,} | In CC Range: {len(staff_cc):,} | High Claimants: {len(staff_high):,}")
