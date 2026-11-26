# Backend

The backend includes the read-only BookOrbit client, encrypted configuration, scanning, a durable delivery outbox, and an early administrator interface. Administration and the runtime are disabled by default and are not yet production-ready.

The Phase-2 schema is managed exclusively by Alembic. From `backend/`, run `alembic upgrade head`; set `BOOKORBIT_NOTIFIER_DATABASE_URL` to select the target SQLite file. The shipped default is only a local development path. Never create tables from application code in production.

The scanner/delivery runtime remains disabled until `BOOKORBIT_NOTIFIER_RUNTIME_ENABLED=true`. Enabling it also requires `BOOKORBIT_NOTIFIER_ENCRYPTION_KEY` with a dedicated Fernet key supplied by the deployment secret store. Migrate the database first; startup deliberately does not create or migrate tables.

Run locally after installing the project dependencies:

```text
uvicorn app.main:app --app-dir backend --reload
```

`POST /api/v1/poc/*` endpoints are disabled unless `BOOKORBIT_NOTIFIER_POC_ENDPOINTS_ENABLED=true` is set. They are development diagnostics only and must never be exposed publicly because they accept transient credentials.

## Local administrator setup

First migrate the database. Enable the interface with `BOOKORBIT_NOTIFIER_ADMIN_ENABLED=true`, set `BOOKORBIT_NOTIFIER_ADMIN_ORIGIN` to the exact browser origin (for example `http://127.0.0.1:8000` for local use), and supply `BOOKORBIT_NOTIFIER_SETUP_TOKEN` as a separate, randomly generated secret of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and keep it out of logs, source control and shared configuration. Open `/admin`, enter the setup token and an administrator password of at least 12 characters, then sign in. Remove the setup token from the environment after setup and restart the service.

Remote access requires an HTTPS origin; plain HTTP is accepted only for localhost or loopback addresses. HTTPS must be provided by the deployment or a trusted reverse proxy, and the configured origin must match the externally visible browser address. Do not enable the development POC routes on an exposed instance. Current views cover setup, login, delivery counts and sender profiles at global, webhook and library level; server management and the remaining Phase 4 screens are not implemented.

The Discord preview uses fixed sample metadata and the same safe renderer as delivery. Its title, description and footer are temporary and are neither saved nor sent; the variable selector lists available placeholders. Actual field availability depends on the BookOrbit version and each book's metadata. The avatar placeholder and inherited sender label do not yet reproduce a Discord webhook's original profile.
