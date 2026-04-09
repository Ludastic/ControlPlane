# Control Plane

FastAPI backend for the Control Plane service.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
Copy-Item .env.example .env
```

Default runtime uses the `database` backend with local SQLite:

```text
CONTROL_PLANE_STORAGE_BACKEND=database
CONTROL_PLANE_DATABASE_URL=sqlite:///./control_plane.db
CONTROL_PLANE_ARTIFACTS_ROOT=.artifacts
CONTROL_PLANE_AGENT_REGISTRATION_TOKEN=bootstrap-secret
CONTROL_PLANE_INVENTORY_RETENTION_LIMIT=5
CONTROL_PLANE_EXECUTION_RETENTION_DAYS=30
CONTROL_PLANE_AUDIT_RETENTION_DAYS=90
CONTROL_PLANE_BOOTSTRAP_ADMIN_USERNAME=
CONTROL_PLANE_BOOTSTRAP_ADMIN_PASSWORD=
```

`memory` backend is still available for isolated tests and local experiments:

```text
CONTROL_PLANE_STORAGE_BACKEND=memory
```

## Database Bootstrap

Apply migrations before the first run. The API no longer auto-creates tables at runtime.

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Local Docker stack with PostgreSQL:

```powershell
docker compose up --build
```

The API becomes available at `http://localhost:8000`, PostgreSQL at `localhost:5432`.

Swagger UI is available at `http://localhost:8000/docs`, ReDoc at `http://localhost:8000/redoc`, and raw OpenAPI schema at `http://localhost:8000/openapi.json`.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Migration validation on a fresh SQLite database:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_migrations.py
```

Optional PostgreSQL verification:

```powershell
$env:CONTROL_PLANE_POSTGRES_TEST_URL='postgresql+psycopg://postgres:postgres@localhost:5432/control_plane_test'
.\.venv\Scripts\python.exe -m pytest -q tests/test_api_postgres.py
```

Cleanup jobs:

```powershell
.\.venv\Scripts\python.exe -m app.jobs.cleanup
```

Containerized cleanup job example:

```powershell
docker compose run --rm api python -m app.jobs.cleanup
```

In `production` mode the service rejects default bootstrap credentials on startup. Set non-default values for `CONTROL_PLANE_ADMIN_JWT_SECRET` and `CONTROL_PLANE_AGENT_REGISTRATION_TOKEN`.
If `CONTROL_PLANE_BOOTSTRAP_ADMIN_USERNAME` and `CONTROL_PLANE_BOOTSTRAP_ADMIN_PASSWORD` are set, the service creates that admin user automatically on database startup if it does not already exist.

## API

- `GET /health`
- `GET /ready`
- `POST /api/v1/agent/register`
- `POST /api/v1/agent/heartbeat`
- `GET /api/v1/agent/desired-state`
- `GET /api/v1/agent/artifacts/{artifact_id}`
- `GET /api/v1/agent/artifacts/{artifact_id}/download`
- `PUT /api/v1/agent/inventory`
- `POST /api/v1/agent/execution-runs`
- `POST /api/v1/agent/execution-runs/{run_id}/events`
- `POST /api/v1/admin/auth/login`
- `POST /api/v1/admin/auth/refresh`
- `POST /api/v1/admin/auth/logout`
- `GET /api/v1/admin/auth/me`
- `GET /api/v1/admin/audit-log`
- `GET /api/v1/admin/hosts`
- `GET /api/v1/admin/hosts/{host_id}`
- `GET /api/v1/admin/hosts/{host_id}/desired-state`
- `GET /api/v1/admin/hosts/{host_id}/inventory`
- `GET /api/v1/admin/hosts/{host_id}/inventory/history`
- `GET /api/v1/admin/hosts/{host_id}/effective-policies`
- `POST /api/v1/admin/hosts/{host_id}/agent-token/rotate`
- `POST /api/v1/admin/hosts/{host_id}/agent-token/revoke`
- `GET /api/v1/admin/execution-runs`
- `CRUD /api/v1/admin/groups`
- `CRUD /api/v1/admin/policies`
- `CRUD /api/v1/admin/policies/{policy_id}/assignments`
- `CRUD /api/v1/admin/policies/{policy_id}/resources`
- `CRUD /api/v1/admin/playbooks`
- `GET/POST /api/v1/admin/playbooks/{playbook_id}/versions`

All HTTP responses include an `X-Request-ID` header. Administrative write actions and auth lifecycle events are recorded in the audit log. `/ready` verifies schema readiness for the database backend and write access to artifact storage.

## CI

The repository includes [ci.yml](C:/Users/ATitlianov/Documents/Учеба/4%20курс/ВКР/code/ControlPlane/.github/workflows/ci.yml), which installs dependencies, runs `alembic upgrade head`, and executes the test suite.
