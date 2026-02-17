# How to check if our system gives correct numbers

## Step 1: Check the FORMULA (5 minutes)

We have a tiny test file where the right answer is known by hand.

**Run:**
```bash
cd /Users/pavanichella/Documents/ABCover
source venv/bin/activate
python check_calculation_correct.py
```

**What you should see:**
- `>>> CORRECT <<<` → The **premium math** (CC days, excess days, commissions, total premium) is right. The formula is not broken.
- `>>> WRONG <<<` → Something in the calculation formula is wrong; we need to fix it.

**What this checks:** Only the calculation formula. No real file, no mapping, no cleaning.

---

## Step 2: Check a REAL file (UI vs script)

After Step 1 passes, you know the formula is correct. Any difference with a real file comes from **data** (column mapping, cleaning, filters).

**Option A – Compare UI vs script**
1. In the **UI**: upload a file (e.g. Elbert.xlsx), do NOT add filters, run cleaning, enter rating inputs (e.g. Deductible 20, CC 60, $150, 15%), click Calculate. Write down: **Total Premium** and **Total CC Days**.
2. Run the **script** with the same file and same inputs:
   ```bash
   python test_with_real_file.py raw_data/Elbert.xlsx --school-name "Elbert"
   ```
3. Compare: script numbers vs UI numbers. They should be the same (or very close; cleaning can vary a bit because of the LLM).

**Option B – Compare UI vs Excel**
1. In Excel (or by hand): take the same file, same filters/cleaning rules, compute total CC days and premium.
2. Run the UI with the same file and same choices.
3. Compare UI numbers to your Excel numbers.

---

## Step 3: Verify School Year Metrics and Total # of Absences

**How "Total # of Absences" is calculated:**
- It is **not** the number of rows. It is the **sum of Absence_Days** for that school year.
- **Absence_Days** per row comes from **Absence Type**: Full Day = 1.0 day, AM/PM Half Day = 0.5 day, Custom Duration = (hours ÷ 7.5) days.
- So for each school year we sum those days → that is "Total # of Absences" for that year.

**How to check the table is correct:**
1. **Spot-check one row:** Total # of Absences × Replacement Cost Per Day = Total Replacement Cost to District.  
   Example: 14,683.79 × 132.30 ≈ 1,942,664.98.
2. **Compare with EDA:** Run the same file in `EDA/test_toms_river.py` (or your notebook) and compare the School Year Metrics table and overall totals with the app.

---

## Summary

| What you want to know | What to do |
|----------------------|------------|
| Is the **formula** correct? | Run `python check_calculation_correct.py`. If it says CORRECT, yes. |
| Is the **full pipeline** (mapping + cleaning + formula) correct for a real file? | Run UI and script on the same file with same inputs; compare Total Premium and CC Days. |
| Are **School Year Metrics** and **Total # of Absences** correct? | In the app, open "How are these numbers calculated? How do I verify?" under the table. Spot-check: Absences × Cost Per Day = Total Replacement Cost. Compare with EDA script/notebook. |

If Step 1 is CORRECT, then the system’s **calculation** is giving correct numbers. Any remaining differences are from how data is mapped or cleaned, not from the premium formula.
