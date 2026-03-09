# How to Find Differences Between Notebook and App Results

If your test notebook results differ from the Streamlit app (UI), use this guide.

## 1. Run the Debug Script

From the project root:

```bash
python EDA/debug_compare_notebook_vs_app.py
```

This script:
- Loads the same Millburn file as the notebook
- Runs notebook-style cleaning (rules + Absence_Days from Absence Type)
- Runs the full app pipeline (upload → select → clean → calculate)
- Compares Total Absence_Days and identifies likely causes

## 2. Common Causes of Mismatch

### Duration vs Absence_Days (most common)

- **Raw "Duration"** = hours (e.g. 7.5 for full day)
- **Absence_Days** should be days (1.0 for full day, 0.5 for half day)
- If the app maps `Duration → Absence_Days` and skips recalculation, hours are treated as days → ~7.5x inflation
- **Fix**: The cleaning agent now always recalculates Absence_Days from Absence Type + Duration when Absence Type exists

### Column mapping

- The app uses agent-suggested or alias mapping in Step 2
- If `Duration` is mapped to `Absence_Days`, the selected data gets hours under the name Absence_Days
- **Fix**: The cleaning agent recalculates Absence_Days from Absence Type when present, ignoring any pre-mapped value

### Filters (date range, employee type)

- The app may apply row filters in Step 2 (date range, employee types)
- The notebook uses no filters
- **Check**: In the app, open "Row Filters" and confirm no filters are applied if you want to match the notebook

### Teacher types

- Notebook: `Teacher`, `Teacher Music`, `Teacher SpecEd`
- App: Same if no employee-type filter; otherwise uses the user’s selection

## 3. Step-by-Step Comparison

| Step              | Notebook                 | App                                   |
|-------------------|--------------------------|----------------------------------------|
| Load              | `pd.read_excel(...)`     | FileUploadAgent                        |
| Clean Rule 1      | Remove Unfilled+NO       | DataCleaningAgentLLM                   |
| Clean Rule 2      | Teacher types only       | DataCleaningAgentLLM (or user filter)  |
| Clean Rule 3      | School Year date check   | DataCleaningAgentLLM                   |
| Absence_Days      | Calc from Absence Type   | DataCleaningAgentLLM (now recalculates)|
| Premium           | Group by Employee ID     | RatingEngineAgentLLM (same logic)      |

## 4. Inline Checks in the App

1. After **Step 2**: Check column mapping. Avoid mapping `Duration` to `Absence_Days`.
2. After **Step 3**: Inspect the preview. Confirm Total Absence_Days is plausible (days, not hours).
3. After **Step 5**: Compare School Year Metrics and premium to the notebook.

## 5. Validation Command

To verify the premium formula against a known answer key:

```bash
python check_calculation_correct.py
```
