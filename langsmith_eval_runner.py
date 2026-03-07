"""
LangSmith evaluation runner: runs ABCover pipeline on a dataset example.
Use this with LangSmith Datasets & Experiments to check if calculations are correct.

Input format (example["inputs"]):
  - file_path: path to CSV/Excel (required)
  - school_name: optional
  - deductible: default 20
  - cc_days: default 60
  - replacement_cost: default 150.0
  - ark_commission_rate: default 0.15
  - abcover_commission_rate: default 0.15
  - school_year_days: default 180
  - filters: optional dict (e.g. {"employee_type": ["Teacher"]})

Output format (returned dict, compare with example["outputs"] reference):
  - total_premium
  - total_cc_days
  - num_staff_cc_range
  - num_high_claimant
  - excess_days
  - overall_total_staff

Usage:
  - From Python (LangSmith experiment target):
      from langsmith_eval_runner import run_abcover
      result = run_abcover({"file_path": "path/to/file.xlsx", "deductible": 20})
  - From CLI (test):
      python langsmith_eval_runner.py path/to/file.xlsx
"""

import os
import sys
import json

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

STANDARD_COLUMNS = [
    "School Year", "Employee Identifier", "Absence_Days", "Date", "School Name",
    "Reason", "Employee Title", "Employee Type", "Absence Type",
    "Start Time", "End Time", "Filled", "Needs Substitute",
]


def run_abcover(inputs: dict) -> dict:
    """
    Run ABCover pipeline and return key metrics.
    Call this from LangSmith experiments (custom runnable) or use directly.

    Args:
        inputs: dict with file_path (required), school_name, deductible, cc_days,
                replacement_cost, ark_commission_rate, abcover_commission_rate,
                school_year_days, filters (optional)

    Returns:
        dict with total_premium, total_cc_days, num_staff_cc_range, etc.
        On error: raises or returns dict with "error" key.
    """
    file_path = inputs.get("file_path")
    if not file_path or not os.path.isfile(file_path):
        return {"error": f"File not found: {file_path}"}

    try:
        ext = file_path.lower().split(".")[-1]
        if ext == "csv":
            df_raw = pd.read_csv(file_path)
        else:
            df_raw = pd.read_excel(file_path)

        from agents.data_analysis_agent import DataAnalysisAgent
        from agents.orchestrator_langgraph import LangGraphOrchestrator, AgentState

        # Column mapping (same as app)
        analysis_agent = DataAnalysisAgent()
        column_map = analysis_agent.suggest_column_mapping(df_raw, STANDARD_COLUMNS)

        state: AgentState = {
            "raw_data": df_raw,
            "selected_columns": df_raw.columns.tolist(),
            "column_map": column_map,
            "filters": inputs.get("filters") or {},
            "school_name": inputs.get("school_name") or "",
            "selected_data": pd.DataFrame(),
            "cleaned_data": pd.DataFrame(),
            "rating_inputs": {},
            "rating_results": {},
            "processing_history": [],
        }

        orch = LangGraphOrchestrator()
        state.update(orch._select_node(state))

        if state.get("selected_data", pd.DataFrame()).empty:
            return {"error": "No data after selection"}

        state.update(orch._clean_node(state))
        cleaned = state.get("cleaned_data", pd.DataFrame())

        if cleaned.empty:
            return {"error": "No data after cleaning"}

        state["rating_inputs"] = {
            "deductible": int(inputs.get("deductible", 20)),
            "cc_days": int(inputs.get("cc_days", 60)),
            "replacement_cost": float(inputs.get("replacement_cost", 150.0)),
            "ark_commission_rate": float(inputs.get("ark_commission_rate", 0.15)),
            "abcover_commission_rate": float(inputs.get("abcover_commission_rate", 0.15)),
            "school_year_days": int(inputs.get("school_year_days", 180)),
        }
        state.update(orch._calculate_node(state))

        results = state.get("rating_results", {})
        if not results:
            return {"error": "No rating results"}

        return {
            "total_premium": round(results.get("total_premium", 0), 2),
            "total_cc_days": round(results.get("total_cc_days", 0), 2),
            "num_staff_cc_range": results.get("num_staff_cc_range", 0),
            "num_high_claimant": results.get("num_high_claimant", 0),
            "excess_days": round(results.get("excess_days", 0), 2),
            "overall_total_staff": results.get("overall_total_staff", 0),
            "below_deductible_count": results.get("below_deductible_count", 0),
        }
    except Exception as e:
        return {"error": str(e)}


def _custom_evaluator(run, example) -> dict:
    """
    Custom evaluator: compare actual vs reference outputs.
    Use in LangSmith as a Custom code evaluator.
    Returns: {"key": "premium_correctness", "score": 1.0 or 0.0, "comment": "..."}
    """
    actual = run.outputs if hasattr(run, "outputs") else {}
    reference = example.outputs if hasattr(example, "outputs") else {}
    if isinstance(actual, str):
        try:
            actual = json.loads(actual)
        except Exception:
            actual = {}
    if isinstance(reference, str):
        try:
            reference = json.loads(reference)
        except Exception:
            reference = {}

    if actual.get("error"):
        return {"key": "premium_correctness", "score": 0.0, "comment": f"Run failed: {actual['error']}"}

    expected_premium = reference.get("total_premium")
    actual_premium = actual.get("total_premium")

    if expected_premium is None:
        return {"key": "premium_correctness", "score": 1.0, "comment": "No reference premium to compare"}

    if actual_premium is None:
        return {"key": "premium_correctness", "score": 0.0, "comment": "No actual premium returned"}

    # Allow 1% tolerance
    tolerance = 0.01
    diff_pct = abs(actual_premium - expected_premium) / expected_premium if expected_premium else 0
    score = 1.0 if diff_pct <= tolerance else 0.0
    comment = f"Actual ${actual_premium:,.2f} vs expected ${expected_premium:,.2f} (diff {diff_pct*100:.2f}%)"
    return {"key": "premium_correctness", "score": score, "comment": comment}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print("Usage: python langsmith_eval_runner.py <file_path>")
        sys.exit(1)
    inputs = {"file_path": path}
    if len(sys.argv) > 2:
        inputs["deductible"] = int(sys.argv[2])
    if len(sys.argv) > 3:
        inputs["cc_days"] = int(sys.argv[3])
    result = run_abcover(inputs)
    print(json.dumps(result, indent=2))
