"""
Run ABCover against your LangSmith dataset (same flow as "Run in SDK").

Prerequisites:
  - LANGCHAIN_API_KEY in .env (or export LANGSMITH_API_KEY)
  - Dataset named "abcover" with examples: inputs (file_path, ...), outputs (reference total_premium, ...)

Usage (from project root):
  source venv/bin/activate
  pip install -U langsmith
  python run_langsmith_experiment.py

Then: LangSmith → Datasets & Experiments → abcover → Experiments
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("LANGCHAIN_API_KEY") and not os.getenv("LANGSMITH_API_KEY"):
    print("Set LANGCHAIN_API_KEY (or LANGSMITH_API_KEY) in .env and try again.")
    sys.exit(1)

# Alias so either env var works
if os.getenv("LANGSMITH_API_KEY") and not os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.environ["LANGSMITH_API_KEY"]


def premium_correctness(outputs: dict, reference_outputs: dict) -> dict:
    """Evaluator: 1.0 if total_premium within 1% of reference, else 0.0.
    LangSmith expects dict with 'key' and 'score' (or 'value')."""
    if outputs.get("error"):
        return {"key": "premium_correctness", "score": 0.0}
    ref = reference_outputs.get("total_premium")
    got = outputs.get("total_premium")
    if ref is None or got is None:
        return {"key": "premium_correctness", "score": 0.0}
    try:
        ref, got = float(ref), float(got)
    except (TypeError, ValueError):
        return {"key": "premium_correctness", "score": 0.0}
    if ref == 0:
        score = 1.0 if got == 0 else 0.0
    else:
        score = 1.0 if abs(got - ref) / ref <= 0.01 else 0.0
    return {"key": "premium_correctness", "score": score}


def main():
    from langsmith import Client
    from langsmith_eval_runner import run_abcover

    client = Client()
    dataset_name = "abcover"

    # 1. Target: your pipeline (inputs dict -> outputs dict)
    # 2. Data: dataset by name (as in "Run in SDK")
    # 3. Evaluators: premium within 1% of reference
    experiment = client.evaluate(
        run_abcover,
        data=dataset_name,
        evaluators=[premium_correctness],
        experiment_prefix="abcover",
        upload_results=True,
    )

    # Optional: print summary
    results = list(experiment)
    n = len(results)
    ok = 0
    for r in results:
        for res in (r.get("evaluation_results") or {}).get("results") or []:
            if getattr(res, "key", None) == "premium_correctness":
                if getattr(res, "score", None) == 1.0:
                    ok += 1
                break
    print(f"Done. Examples: {n}, premium_correctness passed: {ok}/{n}")
    print("LangSmith → Datasets & Experiments → abcover → Experiments")

if __name__ == "__main__":
    main()
