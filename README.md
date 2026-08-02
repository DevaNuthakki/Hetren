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
- Secure project-scoped runner registration and credentials
- Atomic runner-job claiming and lifecycle transitions
- Lease renewal, recovery, cancellation, and structured logs
- Real local ASR job execution through authenticated APIs
- Atomic backend evaluation-result persistence
- One-shot CI runner execution with meaningful exit codes

Phase 3 implements the secure local and CI runner platform, including project-scoped runner operations visibility in the frontend.

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

## Continuous integration

The repository workflow is defined in `.github/workflows/ci.yml`.

It runs for pull requests targeting `main`, pushes to `main`, and manual workflow dispatches.

The backend job starts PostgreSQL 18, creates separate development and test databases, applies and checks Alembic migrations, compiles the backend, and runs both backend test suites.

The frontend job installs dependencies from the committed lockfile, runs linting, and creates the production build.

## Secure runner operations

Phase 3 runner registration, secure job coordination, local polling and
execution, lease recovery, structured execution logging, read-only
project-scoped runner operations APIs and UI, and administrative CLI
instructions are documented in `docs/OVRIN_RUNNER_OPERATIONS.md`.

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

## Secure runner registration

Phase 3.1 provides the secure identity foundation for local and CI runners.

It currently supports:

- Project-scoped runner identities
- High-entropy, one-time registration tokens
- Short registration-token expiration
- Hashed registration-token storage
- Hashed runner-credential storage
- Atomic token consumption and runner creation
- Authenticated heartbeat updates
- Runner capability and system metadata
- Administrative runner revocation
- PostgreSQL lifecycle and project-isolation constraints

Secure job claiming, lifecycle transitions, lease recovery, structured log upload and retrieval, active cooperative cancellation, real ASR execution, atomic evaluation-result submission, one-shot CI runner mode, and repository-level GitHub Actions validation are implemented.

### Security model

An administrator creates a short-lived registration token through a local CLI command.

The plaintext registration token is displayed once. Ovrin stores only its SHA-256 digest.

A runner exchanges the token using:

```text
POST /runners/register
```

A successful registration returns a separate runner credential once. Ovrin stores only the credential digest.

The runner uses that credential as an HTTP Bearer token when calling:

```text
POST /runners/heartbeat
```

Registration-token issuance and runner revocation are intentionally CLI-only. They are not exposed through unauthenticated administrative API endpoints.

Registration succeeds only when the submitted token:

- Has not expired
- Has not already been consumed
- Has not been revoked
- Belongs to the correct project
- Matches the stored token digest

Invalid, expired, consumed, and revoked tokens return the same generic authentication response.

### Issue a registration token

From `backend`:

```bash
python scripts/issue_runner_registration_token.py \
  --project-id 1 \
  --label "Local ASR runner" \
  --ttl-minutes 30
```

The command displays a token beginning with:

```text
ovrin_reg_
```

Store it securely. The plaintext token is not stored by Ovrin and cannot be displayed again.

### Register a runner

With the backend running:

```bash
curl -X POST \
  http://127.0.0.1:8000/runners/register \
  -H "Content-Type: application/json" \
  --data '{
    "registration_token": "ovrin_reg_REPLACE_ME",
    "name": "Local ASR Runner",
    "runner_version": "0.1.0",
    "capabilities": ["asr", "cpu"],
    "system_info": {
      "platform": "darwin",
      "architecture": "arm64"
    }
  }'
```

A successful request returns HTTP `201` with:

- The runner public ID
- Runner status and metadata
- A plaintext credential beginning with `ovrin_runner_`

The plaintext credential is returned only during registration and must be stored securely.

The response does not expose:

- Database runner ID
- Registration-token ID
- Registration-token hash
- Runner-credential hash

### Send a runner heartbeat

```bash
curl -X POST \
  http://127.0.0.1:8000/runners/heartbeat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ovrin_runner_REPLACE_ME" \
  --data '{
    "runner_version": "0.1.1",
    "capabilities": ["asr", "cpu", "local"],
    "system_info": {
      "platform": "darwin",
      "architecture": "arm64"
    }
  }'
```

A successful heartbeat returns HTTP `200` and updates:

- `last_seen_at`
- Runner version, when supplied
- Capabilities, when supplied
- System information, when supplied

Omitted optional metadata remains unchanged.

### Revoke a runner

Use the public ID returned during registration:

```bash
python scripts/revoke_runner.py \
  --runner-public-id "REPLACE_WITH_RUNNER_PUBLIC_ID"
```

Revocation is idempotent and preserves the original revocation timestamp.

After revocation:

- Runner status becomes `revoked`
- `revoked_at` is recorded
- The runner credential can no longer authenticate
- Heartbeat requests return HTTP `401`

### Runner database guarantees

PostgreSQL enforces:

- Unique registration-token hashes
- Unique runner-credential hashes
- Unique runner public IDs
- One runner per registration token
- Unique runner names within a project
- Registration token and runner project matching
- Token expiration after token creation
- Mutually exclusive token consumption and revocation
- Active runners having no revocation timestamp
- Revoked runners having a revocation timestamp

### Production requirements

Production runner communication must additionally use:

- HTTPS only
- Secure secret delivery and storage
- API rate limiting
- Authentication-failure monitoring
- Audit logging without plaintext secrets
- Credential rotation procedures
- Restricted administrative access
- Separate credentials for every runner
- No plaintext tokens or credentials in source control, logs, or configuration files


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
