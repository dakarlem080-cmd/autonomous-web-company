# Autonomous Web Company

Standalone autonomous website operating system.

Loop: Observe -> Discover -> Decide -> Build -> Test -> Release -> Measure -> Learn -> Repeat.

Includes FastAPI, PostgreSQL, Redis, LangGraph, CEO/Research/SEO/Content/Developer/QA/Analyst agents, GSC, GA4, GitHub, Vercel, scheduler, experiments, audit log, encrypted secrets, workspace isolation and dashboard.

## Run

```bash
docker compose up -d
cd backend && python -m venv .venv && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd dashboard
npm install
npm run dev
```

Keep `AUTONOMY_DRY_RUN=true` until credentials and deployment policies are verified.
