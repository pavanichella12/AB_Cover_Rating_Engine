"""
SIMPLE CHECK: Are our calculation numbers correct?

This uses a TINY file where we know the exact right answer (by hand).
- If the script says "CORRECT" -> the premium math in our system is right.
- If it says "WRONG" -> something in the formula is broken.

No LLM, no cleaning. Just: load 4 rows -> run premium formula -> compare to answer key.
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============ ANSWER KEY (hand-calculated) ============
# File: 4 teachers. Deductible=20, CC Days=60, CC Max=80, Replacement=$150/day, Commission=15%
#   Teacher A: 15 days -> below deductible -> NOT in CC
#   Teacher B: 50 days -> in CC -> count 50-20 = 30 days
#   Teacher C: 75 days -> in CC -> count 75-20 = 55 days
#   Teacher D: 100 days -> high claimant -> excess 100-80 = 20 days
# Total CC days = 30 + 55 = 85
# Replacement (CC) = 85 * 150 = 12750
# ARK commission = 12750 * 0.15 = 1912.50
# ABCover commission = 12750 * 0.15 = 1912.50
# TOTAL PREMIUM = 12750 + 1912.50 + 1912.50 = 16575

EXPECTED = {
    "num_staff_cc_range": 2,
    "total_cc_days": 85,
    "replacement_cost_cc": 12750.0,
    "num_high_claimant": 1,
    "excess_days": 20.0,
    "high_claimant_cost": 3000.0,
    "ark_commission": 1912.5,
    "abcover_commission": 1912.5,
    "total_premium": 16575.0,
}


def main():
    path = os.path.join(os.path.dirname(__file__), "ANSWER_KEY_SMALL.csv")
    if not os.path.isfile(path):
        print("ANSWER_KEY_SMALL.csv not found.")
        sys.exit(1)

    df = pd.read_csv(path)
    teacher_days = df.groupby(["School Year", "Employee Identifier"])["Absence_Days"].sum().reset_index()
    teacher_days.columns = ["School Year", "Employee Identifier", "Total_Days"]

    from agents.rating_engine_agent_llm import RatingEngineAgentLLM
    agent = RatingEngineAgentLLM()
    results, _ = agent.process(
        teacher_days,
        df.copy(),
        deductible=20,
        cc_days=60,
        replacement_cost=150.0,
        ark_commission_rate=0.15,
        abcover_commission_rate=0.15,
        school_name="Test",
        blackboard_context=None,
        school_year_days=180,
    )

    all_ok = True
    for key, expected_val in EXPECTED.items():
        actual = results.get(key)
        if actual is None:
            print(f"  Missing: {key}")
            all_ok = False
        elif abs(actual - expected_val) > 0.02:
            print(f"  WRONG {key}: got {actual}, expected {expected_val}")
            all_ok = False

    print()
    if all_ok:
        print(">>> CORRECT <<<")
        print("The premium calculation formula is right for this answer key.")
        print("So: the MATH in our system is correct.")
        print("If your UI shows different numbers for a real file, the difference")
        print("comes from DATA (mapping, cleaning, filters), not from the formula.")
        sys.exit(0)
    else:
        print(">>> WRONG <<<")
        print("Something in the calculation formula does not match the answer key.")
        print("Check the rating engine logic.")
        sys.exit(1)


if __name__ == "__main__":
    main()
