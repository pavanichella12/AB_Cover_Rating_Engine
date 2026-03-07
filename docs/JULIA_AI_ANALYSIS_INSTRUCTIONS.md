# Instructions for Julia's AI: How to Analyze a School Absence File (Start to End)

Use these steps when you are asked to analyze a school absence data file the same way the ABCover system does. Follow them in order.

---

## 1. Understand the file and columns

- The file is usually CSV or Excel with rows = absence records (one row per absence event).
- **Map columns** to these standard names (schools use different names; use column names AND the actual values in each column to decide):
  - **Employee Identifier** – unique staff ID (e.g. A123, 456).
  - **Employee First Name** / **Employee Last Name** – names (for reports).
  - **Date** – the date the absence occurred (not Hire Date).
  - **School Year** – fiscal year like "2020-2021". If missing, derive it from Date (e.g. if Date is in July 2020–June 2021 → "2020-2021").
  - **Absence_Days** – number of days for that absence (0.5, 1, 2, etc.). See step 2 for how to get this if there is no such column.
  - **Duration** – if present, often in **hours** (e.g. 7.5 = one full day).
  - **Start Time** / **End Time** – if present, used to compute duration in hours.
  - **Absence Type** – can be **reason** (Sick, Personal) or **duration type** (Full Day, Half Day). Do not assume it is always duration.
  - **Employee Type** – job type (Teacher, Aide, etc.).
  - **Filled** – e.g. Filled / Unfilled.
  - **Needs Substitute** – e.g. YES / NO.
  - **School Name**, **Reason**, **Employee Title** – optional.

---

## 2. Calculate Absence_Days (number of days per row)

If the file has no column that is already “days per absence,” compute **Absence_Days** for each row using this **priority** (use the first that applies):

1. **Existing days column**  
   If a column is clearly “days” (values like 0.5, 1, 2), use it as **Absence_Days**.

2. **Duration (hours)**  
   If there is a **Duration** column in **hours** (e.g. 7.5, 3.75):  
   **Absence_Days = Duration ÷ 7.5**  
   (7.5 = hours per full day.)

3. **Start Time and End Time**  
   If there are **Start Time** and **End Time**:  
   - Compute duration in hours = (End Time − Start Time) in hours.  
   - **Absence_Days = (duration in hours) ÷ 7.5.**

4. **Absence Type (only if it clearly means duration)**  
   Use **Absence Type** only when it explicitly says something like:
   - "Full Day" → 1.0 day  
   - "AM Half Day" or "PM Half Day" → 0.5 day  
   If **Absence Type** is reason (Sick, Personal, etc.), **do not** use it to set days; use Duration or Start/End Time instead. If nothing applies, treat as 0.

---

## 3. Data cleaning (apply in this order)

**Rule 1 – Unfilled + NO Substitute**  
- Remove rows where **Filled = "Unfilled"** AND **Needs Substitute = "NO"**.  
- If the file uses different values (e.g. "No", "N"), treat equivalents the same way.

**Rule 2 – Employee type filter**  
- Keep only the employee types you care about (e.g. Teacher, Teacher Music, Teacher SpecEd).  
- Drop rows whose **Employee Type** is not in that list.

**Rule 3 – School year and date**  
- **School Year** must be in the form "YYYY-YYYY" (e.g. "2020-2021").  
- That year means: **July 1, first year** to **June 30, second year**.  
- Remove rows where **Date** does not fall in that range for the row’s **School Year**.  
- If **School Year** is missing but **Date** exists, derive School Year from Date (July–June).

After cleaning, you have the **cleaned dataset**. Each row has **Absence_Days** (from step 2).

---

## 4. Per-teacher totals

- Group by **Employee Identifier** and **School Year** (if present).  
- For each teacher in each school year, sum **Absence_Days** to get **Total_Days** (total absence days for that teacher in that year).  
- If there is no School Year, use one “global” group per teacher.

---

## 5. Rating inputs (you need these from the user or the file)

- **Deductible** (days) – e.g. 20.  
- **CC days** – e.g. 60 (number of days in the “CC” band).  
- **CC Maximum** = Deductible + CC days (e.g. 20 + 60 = 80).  
- **Replacement cost per day** – e.g. $250.  
- **ARK commission rate** – e.g. 0.10 (10%).  
- **ABCover commission rate** – e.g. 0.05 (5%).  
- **School year days** (optional) – e.g. 180.

---

## 6. Teacher buckets (per school year if you have it, else overall)

For each school year (or once if no School Year):

- **Below deductible:** teachers with Total_Days **≤ Deductible**.  
- **In CC range:** teachers with Total_Days **> Deductible** and **≤ CC Maximum**.  
- **High claimant:** teachers with Total_Days **> CC Maximum**.

Count how many teachers fall into each bucket.

---

## 7. CC days (only days in the CC range)

- **CC days** are only the days that fall **above the deductible** and **up to CC Maximum** per teacher.  
- For each teacher in the **In CC range** bucket:  
  - **Days in CC range** = min(Total_Days − Deductible, CC Maximum − Deductible).  
  - Example: Deductible=20, CC Maximum=80, teacher has 50 days → 50−20 = **30** CC days.  
  - Example: teacher has 85 days → cap at 80, so 80−20 = **60** CC days.  
- **Total CC days** = sum of “days in CC range” over all teachers in the CC range.

Do **not** count days below the deductible or above CC Maximum as CC days.

---

## 8. Excess days (high claimants only)

- For each **high claimant** (Total_Days > CC Maximum):  
  **Excess days** = Total_Days − CC Maximum.  
- **Total excess days** = sum of these over all high claimants.

---

## 9. Premium calculation

- **Replacement cost for CC** = Total CC days × Replacement cost per day.  
- **ARK commission** = Replacement cost for CC × ARK commission rate.  
- **ABCover commission** = Replacement cost for CC × ABCover commission rate.  
- **Total premium** = Replacement cost for CC + ARK commission + ABCover commission.

(Excess days and high-claimant cost are for reporting; the premium above is based on CC days.)

---

## 10. What to report

- **Per school year (if you have School Year):**  
  For each year: number of teachers, below deductible / in CC range / high claimant, total CC days, total excess days, replacement cost for CC, ARK commission, ABCover commission, total premium.  
- **Overall:** same metrics across all years (or single set if no School Year).  
- **Detail tables (optional):** list of staff in CC range and high claimants with Employee Identifier, first/last name (if available), total days, days in CC or excess, and the exact formula you used (e.g. "min(50−20, 60)=30").

---

## Summary

1. Map columns and identify/calculate **Absence_Days** (priority: existing days → Duration/7.5 → Start/End time/7.5 → Absence Type only if Full/Half Day).  
2. Clean: drop Unfilled+NO Substitute; filter by Employee Type; drop rows where Date is outside School Year.  
3. Sum Absence_Days per teacher (and per school year if present).  
4. Apply Deductible and CC Maximum to get teacher buckets and CC days (only days in range).  
5. Compute excess days for high claimants.  
6. Premium = (CC days × replacement cost) × (1 + ARK rate + ABCover rate).

If you follow these steps, your analysis will match the ABCover system and can be used to validate its results (e.g. in Julia's AI).
