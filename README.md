# Ovrin

Ovrin is a speech AI regression-debugging platform focused initially on automatic speech recognition (ASR/STT).

It helps engineering teams organise evaluation datasets, execute speech-model evaluations, compare baseline and candidate runs, identify regressions, create debug cases, and make release-safety decisions.

## Current capabilities

Ovrin currently supports:

- Projects, datasets, and test cases
- Audio and reference-transcript workflows
- ASR transcription and evaluation
- Word Error Rate (WER) and Character Error Rate (CER)
- Baseline and candidate run comparisons
- Regression detection and transcript differences
- Debug-case workflows
- Configurable release-safety policies
- PASS, WARN, and FAIL release reports
- PostgreSQL persistence
- Alembic database migrations
- API liveness and database-readiness checks
- Isolated PostgreSQL integration testing

Phase 3 is building the secure local and CI runner platform.

## Technology stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic
- pytest

### Frontend

- React
- TypeScript
- Vite

### Local infrastructure

- Docker Desktop
- Docker Compose
- PostgreSQL 18

## Repository structure

```text
ovrin/
├── backend/
│   ├── alembic/
│   ├── app/
│   ├── scripts/
│   ├── tests/
│   ├── alembic.ini
│   ├── requirements.txt
│   └── requirements-dev.txt
├── docker/
│   └── postgres/
│       └── init/
├── frontend/
├── docs/
├── compose.yml
└── .env.example
```

## Local prerequisites

Install:

- Python 3.13
- Node.js and npm
- Docker Desktop
- Git

Docker Desktop must be running before starting PostgreSQL.

## Environment configuration

Create the local environment file:

```bash
cp .env.example .env
```

The `.env` file is ignored by Git and must never be committed.

The default local setup uses:

```text
Development database: ovrin
Test database:        ovrin_test
PostgreSQL port:      5433
```

The credentials in `.env.example` are for local development only. Staging and production must use separately generated credentials managed outside the repository.

## Start PostgreSQL

From the repository root:

```bash
docker compose up -d postgres
docker compose ps
```

The PostgreSQL service should eventually show as `healthy`.

Verify the connection:

```bash
docker compose exec postgres \
  pg_isready -U ovrin -d ovrin
```

## Create the test database

The initializer is idempotent and can be run repeatedly:

```bash
docker compose exec postgres \
  /docker-entrypoint-initdb.d/01-create-test-database.sh
```

Verify both databases:

```bash
docker compose exec -e PAGER=cat postgres \
  psql -U ovrin -d ovrin \
  -c "
SELECT datname
FROM pg_database
WHERE datname IN ('ovrin', 'ovrin_test')
ORDER BY datname;
"
```

## Backend setup

```bash
cd backend

python3.13 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Database migrations

Alembic is the only database schema-management mechanism. FastAPI does not automatically create database tables.

Apply migrations to the development database:

```bash
cd backend
python -m alembic upgrade head
```

Check the current migration:

```bash
python -m alembic current
```

Confirm that the database and SQLAlchemy models match:

```bash
python -m alembic check
```

Expected:

```text
No new upgrade operations detected.
```

### Apply migrations to the test database

From `backend`:

```bash
TEST_DATABASE_URL="$(
  python - <<'PY'
from app.config import get_settings

settings = get_settings()

if settings.test_database_url is None:
    raise SystemExit("TEST_DATABASE_URL is not configured.")

print(settings.test_database_url)
PY
)"

DATABASE_URL="$TEST_DATABASE_URL" \
  python -m alembic upgrade head
```

## Run the backend

From `backend` with the virtual environment active:

```bash
python -m uvicorn app.main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## Health endpoints

### Compatibility health check

```text
GET /health
```

Confirms that the API is responding.

### Liveness check

```text
GET /health/live
```

Confirms that the FastAPI process is alive.

### Readiness check

```text
GET /health/ready
```

Checks PostgreSQL connectivity.

It returns:

- HTTP 200 when PostgreSQL is reachable
- HTTP 503 when PostgreSQL is unavailable

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

Production build:

```bash
npm run build
```

## Backend tests

### Fast test suite

From `backend`:

```bash
python -W error::DeprecationWarning -m pytest -q
```

PostgreSQL-specific tests are skipped unless explicitly enabled.

### PostgreSQL integration tests

Ensure PostgreSQL is healthy and `ovrin_test` has been migrated.

```bash
RUN_POSTGRES_TESTS=1 \
  python -W error::DeprecationWarning \
  -m pytest -q tests/test_postgres_integration.py
```

These tests validate:

- Alembic revision consistency
- PostgreSQL schema availability
- Timezone-aware timestamps
- Foreign-key enforcement
- Unique-constraint enforcement
- Transaction rollback
- Protection against accidentally using the development database

The integration-test fixture refuses to run unless the configured database is exactly `ovrin_test`.

## Validation data

### Phase 1 validation

From `backend`:

```bash
python scripts/seed_phase_one_demo.py
```

This creates a repeatable ASR evaluation, comparison, and debugging workflow.

### Phase 2 validation

```bash
python scripts/seed_phase_two_demo.py
```

This creates repeatable release-safety examples:

- PASS
- WARN
- FAIL

The FAIL project includes a linked debug case.

Both seed scripts can be rerun safely. Existing validation projects are deleted in PostgreSQL-safe dependency order and recreated without duplicate project names.

## Safe Docker commands

Stop containers while preserving local database data:

```bash
docker compose down
```

Restart PostgreSQL:

```bash
docker compose up -d postgres
```

### Destructive local reset

The following command deletes the PostgreSQL volume and all local Ovrin development and test data:

```bash
docker compose down -v
```

Use it only when a complete local reset is intended.

After a destructive reset:

```bash
docker compose up -d postgres

docker compose exec postgres \
  /docker-entrypoint-initdb.d/01-create-test-database.sh

cd backend
python -m alembic upgrade head
```

Apply migrations separately to `ovrin_test` using the test-database migration command above.

## Creating future migrations

After changing SQLAlchemy models:

```bash
cd backend

python -m alembic revision \
  --autogenerate \
  -m "describe the schema change"
```

Review every generated migration before applying it.

Then run:

```bash
python -m alembic upgrade head
python -m alembic check
```

Generated migrations should include a safe downgrade whenever practical.

## Production database expectations

A client-facing Ovrin deployment should use:

- Managed PostgreSQL
- Separate development, test, staging, and production databases
- Unique production credentials
- Encrypted database connections
- Environment-managed secrets
- Restricted network access
- Automated backups
- Tested restoration procedures
- Alembic migrations during deployment
- Database readiness checks
- Availability and resource monitoring

Local Docker Compose credentials must never be reused in staging or production.