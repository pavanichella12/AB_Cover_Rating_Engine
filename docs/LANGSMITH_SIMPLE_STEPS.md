# LangSmith experiment – simple steps

One place for everything. Do these in order.

---

## What this does

- You have a **dataset** in LangSmith called **abcover** with **examples**.
- Each example = one test case: “for this file and these settings, the premium should be this.”
- The script runs your ABCover pipeline on each example and checks: “did we get the right premium?”

---

## Step 1: Set up ONE example in LangSmith

In LangSmith: **Datasets & Experiments** → **abcover** → **Examples** → add (or edit) an example.

### Inputs (what the pipeline gets)

Must be a JSON object. **Required:** `file_path` must be a real path on your Mac where the file lives.

```json
{
  "file_path": "/Users/pavanichella/Documents/ABCover/path/to/your/absence-file.xlsx"
}
```

You can add optional keys; these are the defaults the code uses if you omit them:

| Key | Example | Meaning |
|-----|---------|--------|
| `deductible` | 20 | Deductible days |
| `cc_days` | 60 | Critical illness days |
| `replacement_cost` | 150.0 | Replacement cost |
| `school_year_days` | 180 | School year length |

Example with options:

```json
{
  "file_path": "/Users/pavanichella/Documents/ABCover/data/Millburn.xlsx",
  "deductible": 20,
  "cc_days": 60
}
```

Use a path that exists on your machine (e.g. a file inside your ABCover folder).

### Outputs (reference – what you expect)

This is the “correct answer” you’re comparing against. At minimum you need `total_premium`. Others are optional.

```json
{
  "total_premium": 110800.45,
  "total_cc_days": 596.5,
  "num_staff_cc_range": 36,
  "num_high_claimant": 9
}
```

How to get these numbers: run the pipeline once (e.g. in the Streamlit app or with `python langsmith_eval_runner.py path/to/file.xlsx`), take the output, and paste it here as the reference. Or use numbers from Julia’s analysis.

Summary:

- **Inputs** = `file_path` (+ optional settings).
- **Outputs** = reference numbers, especially `total_premium`.

---

## Step 2: Run the experiment on your machine

In a terminal, from the **ABCover project folder**:

```bash
source venv/bin/activate
python run_langsmith_experiment.py
```

The script will:

1. Read each example’s **inputs**.
2. Call your pipeline (`run_abcover`) with those inputs (so it reads the file and computes premium).
3. Compare the pipeline **output** to the example’s **outputs** (reference).
4. Upload results to LangSmith.

You’ll see a link in the terminal; open it to see the experiment.

---

## Step 3: Look at results in LangSmith

Open the link printed by the script, or go to:

**LangSmith** → **Datasets & Experiments** → **abcover** → **Experiments** → latest run.

For each example you’ll see:

- **Input** (your `file_path` and options).
- **Output** (what the pipeline returned: `total_premium`, etc.).
- **Reference** (what you said it should be).
- **premium_correctness** = 1.0 (within 1% of reference) or 0.0 (not).

---

## If something goes wrong

| Problem | What to check |
|--------|----------------|
| “File not found” | In the example’s **Inputs**, `file_path` must be a full path to a file that exists on the machine where you run `run_langsmith_experiment.py`. |
| “No dataset named abcover” | Create a dataset in LangSmith and name it exactly **abcover**. |
| “Set LANGCHAIN_API_KEY” | Put `LANGCHAIN_API_KEY=your_key` in `.env` in the project root (get the key from LangSmith settings). |
| premium_correctness = 0 | Your reference **Outputs** might not match the pipeline’s logic (e.g. different deductible). Set the reference from a known-good run, or relax the 1% rule in `run_langsmith_experiment.py` (premium_correctness function). |

---

## Quick test without LangSmith

Check that the pipeline runs and returns the shape we expect:

```bash
python langsmith_eval_runner.py "/full/path/to/your/file.xlsx"
```

You should see JSON with `total_premium`, `total_cc_days`, etc. That same structure is what each example’s **Outputs** should have (with the values you consider correct).
