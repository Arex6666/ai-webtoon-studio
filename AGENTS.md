# Repository Guidelines

## Project Structure & Module Organization
This repository is a monorepo with two primary apps:
- `apps/web`: Next.js 14 + TypeScript frontend (`src/app`, `src/components`, `src/lib`, `src/hooks`).
- `apps/api`: FastAPI backend (`app/api/routes`, `app/models`, `app/schemas`, `app/services`, `app/workers`).

Supporting directories:
- `apps/api/migrations`: Alembic database migrations.
- `docker/`: local infrastructure (`docker-compose.yml` for PostgreSQL, Redis, MinIO).
- `tests/` and `apps/api/tests/`: integration and backend unit tests.
- `docs/`: specs and format references.

## Build, Test, and Development Commands
- `cd docker && docker compose up -d postgres redis minio`: start local dependencies.
- `cd apps/api && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`: run backend API.
- `cd apps/api && celery -A app.celery_app:celery_app worker --loglevel=info --pool=solo`: run async worker.
- `cd apps/web && npm install && npm run dev`: run frontend on port `3001`.
- `cd apps/web && npm run lint`: run Next.js/ESLint checks.
- `cd apps/web && npm run build`: create production frontend build.
- `cd apps/api && pytest`: run backend tests (`pytest tests/unit -q` for faster unit-only runs).

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for modules/functions, `PascalCase` for classes.
- TypeScript/React: 2-space indentation, `PascalCase` component files (for example, `AgentChat.tsx`), `camelCase` hooks/utilities (`useOrchestrator.ts`, `client.ts`).
- Keep route/module names descriptive and aligned with existing folder domains (`assets`, `chapters`, `layer_factory`, `conversation`).

## Testing Guidelines
- Primary framework: `pytest` with `pytest-asyncio` for async paths.
- Name tests as `test_*.py`; keep unit tests under `apps/api/tests/unit/<domain>/`.
- Add integration coverage when changing cross-module behavior (API + worker + DB).
- No fixed coverage threshold is enforced yet; new features should include at least one happy-path and one failure-path test.

## Commit & Pull Request Guidelines
- Current history is minimal (`Initial commit: AI Webtoon Studio`), so keep commits short, imperative, and scoped (example: `api: fix export bundle status update`).
- One logical change per commit; include migration files with related model changes.
- PRs should include: summary, impacted paths, test commands run, and screenshots/GIFs for UI updates.
- Link related issues and call out env/config changes (`.env`, ports, external services) explicitly.
