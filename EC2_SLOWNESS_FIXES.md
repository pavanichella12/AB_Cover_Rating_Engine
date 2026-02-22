# EC2 Slowness – What to Check and Fix

Deployment works but the URL is **very slow**. Do these in order.

---

## 1. Instance size (most common cause)

**Too small instance = very slow.**

| Instance        | RAM   | Use for this app?        |
|-----------------|-------|---------------------------|
| t2.micro / t3.micro | 1 GB  | **No** – too small        |
| t3.small        | 2 GB  | **Minimum** for Streamlit + LangChain |
| t3.medium       | 4 GB  | **Recommended**           |

**What to do:** In AWS Console → EC2 → select your instance → **Actions → Instance settings → Change instance type** → choose **t3.small** or **t3.medium** → Apply. Stop the instance before changing type.

---

## 2. How you run Docker

Give the container enough memory and run in the foreground so the app stays up.

**Recommended run command on EC2:**

```bash
docker run -d --restart unless-stopped -p 8501:8501 --memory="1.5g" --env-file .env --name abcover abcover
```

- `--memory="1.5g"` – avoids OOM and slowdowns.
- `--restart unless-stopped` – container comes back after reboot.

If you run **without** `-d`, the process can die when you close SSH. Use `-d` (detached) for a long‑running app.

---

## 3. First request is always slower (cold start)

The first time someone opens the URL after a while, Python + Streamlit + LangChain load. That can take 15–30 seconds on a small instance.

**What to do:**

- Use at least **t3.small** (better t3.medium).
- Optionally run a **keep‑warm** request every 5 minutes (e.g. cron calling `curl -s -o /dev/null http://localhost:8501` on the server).

---

## 4. Where the instance runs

If users are far from the EC2 region, the **network** is slow even if the server is fast.

**What to do:** Choose a region close to your users (e.g. US East if users are on the East Coast). You can create a new instance in that region and deploy the same Docker image there.

---

## 5. Changes already made in this repo (after you pull)

- **.streamlit/config.toml:** `runOnSave = false`, `headless = true` – fewer reloads and better for production.
- **app.py:** Removed blocking Google Fonts import so the first page can render faster.

After pulling, rebuild the image and restart the container:

```bash
cd /path/to/ABCover   # or clone from GitHub again
docker build -t abcover .
docker stop abcover 2>/dev/null; docker rm abcover 2>/dev/null
docker run -d --restart unless-stopped -p 8501:8501 --memory="1.5g" --env-file .env --name abcover abcover
```

---

## Quick checklist

1. [ ] Instance type **t3.small** or **t3.medium** (not t2.micro/t3.micro).
2. [ ] Docker run with `--memory="1.5g"` and `-d --restart unless-stopped`.
3. [ ] Pull latest code, rebuild image, restart container (for config/font changes).
4. [ ] If still slow, try **t3.medium** or a region closer to users.

Most “very slow” EC2 setups are fixed by **upgrading to t3.small (or t3.medium) and giving the container 1.5G memory**.
