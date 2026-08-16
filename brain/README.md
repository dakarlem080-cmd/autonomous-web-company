# Autonomous Brain

The autonomous control plane. This service owns AI agents, data integrations, scheduling, memory, decisions and publishing credentials.

Deploy this service separately from the dashboard. Never put its secrets in the Vercel dashboard deployment.

## Required runtime secrets

See `.env.example`. In particular, `VERCEL_TOKEN`, `GITHUB_TOKEN`, Google credentials and `OPENAI_API_KEY` belong here only.

## Safety

Start with `AUTONOMY_DRY_RUN=true`. Enable production publishing only after validating the target project and change budget.
