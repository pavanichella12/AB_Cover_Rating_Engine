"""
Debug: Compare Test Notebook results vs App (UI) results.

Run this to find where numbers diverge between the notebook and the Streamlit app.
Usage: python EDA/debug_compare_notebook_vs_app.py

Common causes of mismatch:
1. Duration vs Absence_Days: Raw "Duration" is HOURS (e.g. 7.5). When mapped to Absence_Days in the app,
   it's used as days → inflates by ~7.5x. Notebook correctly converts via Absence Type (Full Day=1.0).
2. Column mapping: App uses agent/alias mapping. If "Duration" → "Absence_Days", app uses hours as days.
3. Teacher aggregation: App groups by (School Year, Employee Identifier) then sums. Notebook groups by
   Employee Identifier only. Both should yield same total per teacher across years.
4. Filters: App may apply date range or employee type filters in Step 2; notebook uses none.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from agents.orchestrator_langgraph import LangGraphOrchestrator

# Same file as test notebook
FILE_PATH = os.path.join(os.path.dirname(__file__), "../raw_data/16618 - Millburn Absence History 7.1.20 to 6.30.25.xlsx")
if not os.path.isfile(FILE_PATH):
    print(f"File not found: {FILE_PATH}")
    sys.exit(1)

print("=" * 60)
print("DEBUG: Notebook vs App Comparison")
print("=" * 60)

# Load raw (like notebook cell 0)
df_raw = pd.read_excel(FILE_PATH)
print(f"\n1. RAW DATA: {len(df_raw)} rows, {len(df_raw.columns)} cols")
print(f"   Columns: {list(df_raw.columns)}")

# Check for Duration vs Percent of Day
if "Duration" in df_raw.columns:
    dur_sample = df_raw["Duration"].dropna().head(5).tolist()
    print(f"   Duration sample (likely HOURS): {dur_sample}")
    print(f"   Duration max: {df_raw['Duration'].max()}")
if "Percent of Day" in df_raw.columns:
    print("   Has 'Percent of Day' (actual days) - prefer this over Duration")

# Notebook-style cleaning (like test.ipynb cell 2)
df_clean_nb = df_raw.copy()
df_clean_nb = df_clean_nb[~((df_clean_nb["Filled"] == "Unfilled") & (df_clean_nb["Needs Substitute"] == "NO"))]
df_clean_nb = df_clean_nb[df_clean_nb["Employee Type"].isin(["Teacher", "Teacher Music", "Teacher SpecEd"])]
df_clean_nb["Date"] = pd.to_datetime(df_clean_nb["Date"], errors="coerce")

def date_in_school_year(row):
    sy = str(row["School Year"]).split("-")
    if len(sy) != 2:
        return True
    start_year, end_year = int(sy[0]), int(sy[1])
    start = pd.Timestamp(year=start_year, month=7, day=1)
    end = pd.Timestamp(year=end_year, month=6, day=30)
    return start <= row["Date"] <= end

df_clean_nb = df_clean_nb[df_clean_nb.apply(date_in_school_year, axis=1)]

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

df_clean_nb["Absence_Days"] = df_clean_nb.apply(calc_absence_days, axis=1)
print(f"\n2. NOTEBOOK CLEANED: {len(df_clean_nb)} rows")
nb_total_abs = df_clean_nb["Absence_Days"].sum()
print(f"   Total Absence_Days (calculated from Absence Type): {nb_total_abs:,.2f}")

# Run app pipeline (orchestrator)
from io import BytesIO
with open(FILE_PATH, "rb") as f:
    upload_obj = BytesIO(f.read())
upload_obj.name = os.path.basename(FILE_PATH)

orch = LangGraphOrchestrator()
# Build state like app does: upload -> select -> clean -> calculate
state = {
    "uploaded_file": upload_obj,
    "raw_data": pd.DataFrame(),
    "selected_data": pd.DataFrame(),
    "cleaned_data": pd.DataFrame(),
    "selected_columns": df_raw.columns.tolist(),
    "column_map": {},  # No mapping - use raw column names
    "filters": {},
    "school_name": "Millburn",
    "rating_inputs": {
        "deductible": 20,
        "cc_days": 60,
        "replacement_cost": 150.0,
        "ark_commission_rate": 0.15,
        "abcover_commission_rate": 0.15,
        "school_year_days": 180,
    },
    "processing_history": [],
}

# Run each node manually (merge updates)
state.update(orch._upload_node(state))
print(f"\n3. APP UPLOAD: {len(state['raw_data'])} rows")

state["selected_columns"] = state["raw_data"].columns.tolist()
state["column_map"] = {}  # No mapping - raw names
state.update(orch._select_node(state))
print(f"4. APP SELECT: {len(state['selected_data'])} rows")
print(f"   Selected cols: {list(state['selected_data'].columns)}")
if "Absence_Days" in state["selected_data"].columns:
    app_abs_before_clean = state["selected_data"]["Absence_Days"].sum()
    print(f"   Sum of 'Absence_Days' in selected_data: {app_abs_before_clean:,.2f}")
elif "Duration" in state["selected_data"].columns:
    print("   Selected has 'Duration' (hours) - will be used for Absence_Days in calc")

state.update(orch._clean_node(state))
print(f"5. APP CLEAN: {len(state['cleaned_data'])} rows")
app_total_abs = state["cleaned_data"]["Absence_Days"].sum() if "Absence_Days" in state["cleaned_data"].columns else 0
print(f"   Total Absence_Days in cleaned_data: {app_total_abs:,.2f}")

state.update(orch._calculate_node(state))
results = state.get("rating_results", {})
print(f"\n6. APP PREMIUM: ${results.get('total_premium', 0):,.2f}")
print(f"   Per-school-year staff: {results.get('per_school_year_metrics', {})}")

# Compare
print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
print(f"Notebook Total Absence_Days: {nb_total_abs:,.2f}")
print(f"App Total Absence_Days:      {app_total_abs:,.2f}")
ratio = app_total_abs / nb_total_abs if nb_total_abs else 0
print(f"Ratio (App/Notebook):        {ratio:.2f}x")
if 6 < ratio < 9:
    print("\n>>> LIKELY CAUSE: App is using Duration (hours) as Absence_Days.")
    print("    Fix: Do NOT map 'Duration' to 'Absence_Days'. Use Absence Type + Duration")
    print("    to calculate Absence_Days in cleaning (Full Day=1.0, Half=0.5, Custom=hrs/7.5).")
elif abs(ratio - 1) > 0.05:
    print("\n>>> Numbers differ - check column mapping, filters, or cleaning rules.")
else:
    print("\n>>> Numbers match closely.")
