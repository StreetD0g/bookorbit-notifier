# Backend

The initial backend is a technical proof of concept. It deliberately contains only the read-only BookOrbit client, Discord webhook transport, and guarded diagnostic endpoints. Persistent configuration, local authentication, encryption, scanning, and the delivery outbox arrive in later phases.

The Phase-2 schema is managed exclusively by Alembic. From `backend/`, run `alembic upgrade head`; set `BOOKORBIT_NOTIFIER_DATABASE_URL` to select the target SQLite file. The shipped default is only a local development path. Never create tables from application code in production.

Run locally after installing the project dependencies:

```text
uvicorn app.main:app --app-dir backend --reload
```

`POST /api/v1/poc/*` endpoints are disabled unless `BOOKORBIT_NOTIFIER_POC_ENDPOINTS_ENABLED=true` is set. They are development diagnostics only and must never be exposed publicly because they accept transient credentials.
