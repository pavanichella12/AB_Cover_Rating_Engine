# LangSmith Evaluation Guide – Check ABCover Calculations

Use this to run ABCover in LangSmith Datasets & Experiments and verify premium/CC days are correct.

---

## 1. Fill example inputs

For each example in your LangSmith dataset:

**Inputs** (JSON or key-value):

```json
{
  "file_path": "/absolute/path/to/your/file.xlsx",
  "school_name": "Millburn",
  "deductible": 20,
  "cc_days": 60,
  "replacement_cost": 150.0,
  "ark_commission_rate": 0.15,
  "abcover_commission_rate": 0.15,
  "school_year_days": 180
}
```

- **file_path**: Required. Use the full path to the file (e.g. `/Users/you/ABCover/raw_data/16618 - Millburn.xlsx`).
- Other fields are optional; defaults above are used if omitted.

**Reference outputs** (what you expect; use a known-good run or manual/Excel calc):

```json
{
  "total_premium": 110800.45,
  "total_cc_days": 596.5,
  "num_staff_cc_range": 36,
  "num_high_claimant": 9
}
```

Add these as "Reference Outputs" for each example.

---

## 2. Test the runner locally

From the project root:

```bash
python langsmith_eval_runner.py "path/to/your/file.xlsx"
```

You should see JSON output with `total_premium`, `total_cc_days`, etc. This is what LangSmith will compare against your reference.

---

## 3. Wire the runner to LangSmith

**Option A: LangSmith UI – Custom Python target**

In LangSmith, when creating an experiment:

- Set **Target** to "Custom" or "Python".
- Use a function that loads `run_abcover` from `langsmith_eval_runner` and calls it with the example inputs.

Example (what you pass as the runnable):

```python
from langsmith_eval_runner import run_abcover

def target(example):
    return run_abcover(example.inputs)
```

(Exact field names depend on LangSmith’s UI; use `example.inputs` or the equivalent.)

**Option B: LangSmith SDK / Python**

If using the LangSmith Python client:

```python
from langsmith import Client
from langsmith_eval_runner import run_abcover

client = Client()
# Run experiment on dataset, using run_abcover as the target
# (See LangSmith docs for run_on_dataset / run_experiment)
```

---

## 4. Add a custom evaluator

In LangSmith: **+ Evaluator** → **Custom code**.

Use this logic (or equivalent) to compare actual vs reference premium:

```python
def evaluate(run, example):
    actual = run.outputs or {}
    reference = example.outputs or {}
    expected = reference.get("total_premium")
    actual_val = actual.get("total_premium")
    if actual.get("error"):
        return {"score": 0, "comment": actual["error"]}
    if expected is None:
        return {"score": 1, "comment": "No reference to compare"}
    if actual_val is None:
        return {"score": 0, "comment": "No premium returned"}
    diff_pct = abs(actual_val - expected) / expected
    score = 1.0 if diff_pct <= 0.01 else 0.0
    return {"score": score, "comment": f"Actual ${actual_val:,.2f} vs expected ${expected:,.2f}"}
```

LangSmith will use this to score each run against the reference outputs.

---

## 5. Run the experiment

- Select your dataset (e.g. `abcover`).
- Set the target to the `run_abcover`-based runnable (Step 3).
- Add the custom evaluator (Step 4).
- Run the experiment.

Each example will show actual vs reference and the evaluator score. Use this to verify your calculations in LangSmith.
