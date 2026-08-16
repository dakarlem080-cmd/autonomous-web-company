# Autonomous Web Company

Standalone autonomous website operating system.

## Architecture

The system is split into two trust boundaries:

- `brain/` — autonomous control plane: AI agents, orchestration, integrations, scheduling, memory and publishing credentials.
- `dashboard/` — thin Next.js control UI. It contains no provider secrets and talks to the brain through `NEXT_PUBLIC_API_URL`.

The brain can manage multiple target websites independently of this dashboard.

## Vercel deployment

Deploy **only `dashboard/`** to Vercel. Set Vercel Root Directory to `dashboard` and add only:

```env
NEXT_PUBLIC_API_URL=https://YOUR-BRAIN-API.example.com
```

Do **not** add `VERCEL_TOKEN`, `VERCEL_PROJECT_ID`, `VERCEL_TEAM_ID`, `GITHUB_TOKEN`, Google credentials or `OPENAI_API_KEY` to the dashboard deployment.

## Brain deployment

Run the autonomous brain as a separate backend/worker service. Its secrets live in `brain/.env` or the backend provider's secret manager. See `brain/.env.example`.

Important secrets include:

```env
OPENAI_API_KEY=
GITHUB_TOKEN=
GOOGLE_APPLICATION_CREDENTIALS=
VERCEL_TOKEN=
DATABASE_URL=
ENCRYPTION_KEY=
```

Start with `AUTONOMY_DRY_RUN=true`. Enable production publishing only after credentials, target repositories and change budgets are verified.

## Local development

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
