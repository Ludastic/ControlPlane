# Control Plane

Minimal FastAPI backend skeleton for the Control Plane service.

## Run

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -e .
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

For local development with test dependencies:

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -e .[dev]
```

## Test

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q
```

## API

- `GET /health`
- `POST /api/v1/agent/register`
- `POST /api/v1/agent/heartbeat`
- `GET /api/v1/agent/desired-state`
- `PUT /api/v1/agent/inventory`
- `POST /api/v1/agent/execution-runs`
- `POST /api/v1/agent/execution-runs/{run_id}/events`
- `POST /api/v1/admin/auth/login`
- `GET /api/v1/admin/hosts`
- `GET /api/v1/admin/hosts/{host_id}`
- `GET /api/v1/admin/hosts/{host_id}/desired-state`
- `GET /api/v1/admin/hosts/{host_id}/inventory`
- `GET /api/v1/admin/hosts/{host_id}/effective-policies`
- `GET /api/v1/admin/execution-runs`
- `CRUD /api/v1/admin/groups`
- `CRUD /api/v1/admin/policies`
- `CRUD /api/v1/admin/policies/{policy_id}/assignments`
- `CRUD /api/v1/admin/policies/{policy_id}/resources`
- `CRUD /api/v1/admin/playbooks`
- `GET/POST /api/v1/admin/playbooks/{playbook_id}/versions`
