# Backend

The initial backend is a technical proof of concept. It deliberately contains only the read-only BookOrbit client, Discord webhook transport, and guarded diagnostic endpoints. Persistent configuration, local authentication, encryption, scanning, and the delivery outbox arrive in later phases.

Run locally after installing the project dependencies:

```text
uvicorn app.main:app --app-dir backend --reload
```

`POST /api/v1/poc/*` endpoints are disabled unless `BOOKORBIT_NOTIFIER_POC_ENDPOINTS_ENABLED=true` is set. They are development diagnostics only and must never be exposed publicly because they accept transient credentials.
