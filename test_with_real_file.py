"""
Test premium calculation using the EXACT same pipeline as the app:
upload -> column mapping (agent) -> selection + filters -> cleaning (LLM) -> calculation.

Run: python test_with_real_file.py [path_to_file] [--school-name "Name"] [--no-clean]
Example: python test_with_real_file.py raw_data/Elbert.xlsx --school-name "Elbert"

Use --no-clean to skip the cleaning step (selection + mapping only) for faster runs.
"""

import os
import sys
import argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Standard column names (same as app.py)
STANDARD_COLUMNS = [
    "School Year", "Employee Identifier", "Absence_Days", "Date", "School Name",
    "Reason", "Employee Title", "Employee Type", "Absence Type",
    "Start Time", "End Time", "Filled", "Needs Substitute",
]


def load_file(path: str) -> pd.DataFrame:
    ext = path.lower().split(".")[-1]
    if ext == "csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def main():
    parser = argparse.ArgumentParser(description="Test premium with same logic as UI")
    parser.add_argument("file", nargs="?", help="Path to CSV/Excel (e.g. raw_data/Elbert.xlsx)")
    parser.add_argument("--school-name", default="", help="School name for cleaning step")
    parser.add_argument("--no-clean", action="store_true", help="Skip cleaning step (mapping + filters only)")
    parser.add_argument("--deductible", type=int, default=20)
    parser.add_argument("--cc-days", type=int, default=60)
    parser.add_argument("--replacement-cost", type=float, default=150.0)
    parser.add_argument("--commission", type=float, default=0.15)
    parser.add_argument("--school-year-days", type=int, default=180)
    args = parser.parse_args()

    raw_dir = os.path.join(os.path.dirname(__file__), "raw_data")
    if args.file:
        path = args.file
    else:
        files = [f for f in os.listdir(raw_dir) if f.endswith(".xlsx") and not f.startswith("~")]
        if not files:
            print("No .xlsx in raw_data. Run: python test_with_real_file.py raw_data/YourFile.xlsx")
            sys.exit(1)
        path = os.path.join(raw_dir, files[0])

    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)

    print("=" * 60)
    print("PREMIUM TEST (same pipeline as UI: map -> select -> clean -> calculate)")
    print("=" * 60)
    print(f"File: {path}")
    print(f"School name: {args.school_name or '(none)'}")
    print(f"Skip cleaning: {args.no_clean}")
    print()

    # 1. Load (same as upload)
    df_raw = load_file(path)
    print(f"[1] Loaded: {len(df_raw):,} rows, {len(df_raw.columns)} columns")

    # 2. Column mapping (same agent as UI)
    from agents.data_analysis_agent import DataAnalysisAgent
    analysis_agent = DataAnalysisAgent()
    column_map = analysis_agent.suggest_column_mapping(df_raw, STANDARD_COLUMNS)
    print(f"[2] Agent column mapping: {len(column_map)} columns mapped")
    for orig, std in list(column_map.items())[:8]:
        print(f"     {orig} -> {std}")
    if len(column_map) > 8:
        print(f"     ... and {len(column_map) - 8} more")

    # 3. Build state and run orchestrator nodes (same as UI)
    from agents.orchestrator_langgraph import LangGraphOrchestrator, AgentState

    state: AgentState = {
        "raw_data": df_raw,
        "selected_columns": df_raw.columns.tolist(),
        "column_map": column_map,
        "filters": {},  # no date/employee filter by default
        "school_name": args.school_name,
        "selected_data": pd.DataFrame(),
        "cleaned_data": pd.DataFrame(),
        "rating_inputs": {},
        "rating_results": {},
        "processing_history": [],
    }

    orch = LangGraphOrchestrator()

    # Select (apply mapping + filters)
    state.update(orch._select_node(state))
    selected = state.get("selected_data", pd.DataFrame())
    print(f"[3] After select: {len(selected):,} rows, {list(selected.columns)}")

    # Clean (LLM cleaning rules - same as UI)
    if not args.no_clean and not selected.empty:
        state.update(orch._clean_node(state))
        cleaned = state.get("cleaned_data", pd.DataFrame())
        print(f"[4] After clean: {len(cleaned):,} rows")
    else:
        state["cleaned_data"] = selected
        print("[4] Clean skipped (using selected data as cleaned)")

    cleaned = state.get("cleaned_data", pd.DataFrame())
    if cleaned.empty:
        print("No data after pipeline. Check mapping/cleaning.")
        sys.exit(1)

    # 5. Rating inputs (same defaults as UI)
    state["rating_inputs"] = {
        "deductible": args.deductible,
        "cc_days": args.cc_days,
        "replacement_cost": args.replacement_cost,
        "ark_commission_rate": args.commission,
        "abcover_commission_rate": args.commission,
        "school_year_days": args.school_year_days,
    }

    # Calculate (same as UI)
    state.update(orch._calculate_node(state))
    results = state.get("rating_results", {})

    if not results:
        print("Calculation produced no results. Check required columns (School Year, Employee Identifier, Absence_Days).")
        sys.exit(1)

    print()
    print("RESULTS (compare with UI)")
    print("-" * 60)
    print(f"Staff in CC Range:        {results.get('num_staff_cc_range', 0)}")
    print(f"Total CC Days:            {results.get('total_cc_days', 0):,.2f}")
    print(f"Replacement Cost (CC):    ${results.get('replacement_cost_cc', 0):,.2f}")
    print(f"High Claimant Staff:     {results.get('num_high_claimant', 0)}")
    print(f"Excess Days:              {results.get('excess_days', 0):,.2f}")
    print(f"ARK Commission:          ${results.get('ark_commission', 0):,.2f}")
    print(f"ABCover Commission:      ${results.get('abcover_commission', 0):,.2f}")
    print(f"TOTAL PREMIUM:           ${results.get('total_premium', 0):,.2f}")
    if results.get("per_school_year_metrics"):
        print()
        print("Per school year:")
        for sy, m in results["per_school_year_metrics"].items():
            print(f"  {sy}: Staff={m['total_staff']}, Absence days={m['total_absences']:,.2f}, Replacement=${m['total_replacement_cost']:,.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
