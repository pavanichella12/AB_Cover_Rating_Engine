# Docker

- **Dockerfile** – Image for the ABCover app (used by CI/CD and for local runs).
- **docker-compose.yml** – Local run with volume for data.

**Build image (from project root):**
```bash
docker build -f docker/Dockerfile -t abcover .
```

**Run with compose (from project root):**
```bash
docker compose -f docker/docker-compose.yml up --build
```
Then open http://localhost:8501.

**.dockerignore** stays at project root so the build context can use it.
