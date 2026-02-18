# GitHub and Future Updates

## 1. Push to GitHub first?

**Yes.** You should push your project to GitHub before deploying. Why:

- **AWS (and most hosts)** need your code from somewhere. They can pull from GitHub (or you build Docker on your laptop and push the image; GitHub is simpler).
- **Future updates** = change code on your laptop → push to GitHub → server pulls and redeploys. No GitHub means no smooth “push and it updates.”

So: create a repo on GitHub, then push this folder (with the files that are **not** in `.gitignore`).

---

## 2. What does NOT get pushed (unnecessary / sensitive)

Your `.gitignore` is set up so these **never** go to GitHub:

| Not pushed | Why |
|------------|-----|
| `venv/`, `env/` | Virtual environment (recreate with `pip install -r requirements.txt`) |
| `.env`, `*.env` | **Secrets** (API keys). Set these on AWS, not in repo. |
| `abcover_users.db` | User database (private; create fresh on server if needed) |
| `logs/` | Log files (can be large) |
| `*.xlsx`, `*.xls`, `*.csv` (except under `raw_data/`) | Data files you don’t want in repo |
| `*.pdf` | Large binaries (e.g. 20-21.pdf) |
| `.cursor/` | Cursor agents/rules (optional; remove from .gitignore if you want to share them) |
| `__pycache__/`, `.DS_Store`, `.idea/`, `.vscode/` | Cache and IDE junk |

So: **no secrets, no venv, no DB, no logs** on GitHub. Only code, `requirements.txt`, `.streamlit`, and any data you explicitly allow (e.g. `raw_data/`, `ANSWER_KEY_SMALL.csv`).

---

## 3. How to switch to a different LLM

Your app already supports **Google (Gemini), OpenAI, Anthropic, and AWS Bedrock**. You don’t change code for that—only **environment variables**.

- **Current (Google):**  
  `GOOGLE_API_KEY=...`  
  (and optionally `LLM_PROVIDER=google`)

- **Switch to OpenAI:**  
  Set on AWS (or in `.env` locally):  
  `LLM_PROVIDER=openai`  
  `OPENAI_API_KEY=...`

- **Switch to Anthropic:**  
  Set on AWS (or in `.env` locally):  
  `LLM_PROVIDER=anthropic`  
  `ANTHROPIC_API_KEY=...`

- **Switch to AWS Bedrock (Claude 3.5 Sonnet):**  
  Set on AWS (or in `.env` locally):  
  `LLM_PROVIDER=bedrock`  
  `LLM_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0` (optional; this is the default)  
  `AWS_REGION=us-east-1` (optional; default is `us-east-1`)  
  AWS credentials: use an **IAM role** on EC2/ECS/Lambda, or set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Ensure the role/user has `bedrock:InvokeModel` and model access enabled in the Bedrock console.

The code in `agents/llm_agent_base.py` and `agents/orchestrator_langgraph.py` reads `LLM_PROVIDER` and the right API key (or AWS credentials for Bedrock). So:

1. Add the new API key in AWS (e.g. App Runner / EC2 environment variables), or for Bedrock attach an IAM role with Bedrock access.
2. Set `LLM_PROVIDER=openai`, `LLM_PROVIDER=anthropic`, or `LLM_PROVIDER=bedrock`.
3. Redeploy or restart the app (so it picks up the new env vars).

No need to push new code unless you add a new provider in code.

---

## 4. How to update any code in the future

Same idea for **any** change (new feature, bug fix, UI, logic):

1. **Edit on your laptop** in this project.
2. **Test locally** (e.g. `streamlit run app.py`).
3. **Commit and push to GitHub:**
   ```bash
   git add .
   git commit -m "Describe your change"
   git push origin main
   ```
4. **On AWS:**
   - **If you use App Runner (or similar)** with “deploy on push”: it will automatically rebuild and deploy. You do nothing else.
   - **If you use EC2 + Docker:** SSH into the server, then:
     ```bash
     cd /path/to/your/app
     git pull origin main
     docker build -t abcover .
     docker stop abcover-app && docker rm abcover-app
     docker run -d --name abcover-app -p 8501:8501 -e GOOGLE_API_KEY=... abcover
     ```
     (You can put those commands in a small script so “update” = `./redeploy.sh`.)

So: **update code → push to GitHub → AWS either auto-deploys or you pull + rebuild + restart.** No need to redo the whole deployment from scratch.
