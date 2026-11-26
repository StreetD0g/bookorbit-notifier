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

Remote access requires an HTTPS origin; plain HTTP is accepted only for localhost or loopback addresses. HTTPS must be provided by the deployment or a trusted reverse proxy, and the configured origin must match the externally visible browser address. Do not enable the development POC routes on an exposed instance. The UI supports setup, login, delivery counts, adding and editing sources and webhooks, discovering libraries, routing and sender profiles. Removing sources and the remaining Phase 4 screens are not implemented. Adding or routing sources and destinations requires a dedicated `BOOKORBIT_NOTIFIER_ENCRYPTION_KEY` even if the scheduler is disabled; keep that key backed up separately from the database.

Existing server URLs cannot be changed in place because existing library and book IDs belong to that source; create a new server configuration for another instance. Rotating a stored webhook URL requires explicit confirmation because pending deliveries will use the replacement destination. A manual scan is available only with the opt-in runtime enabled; it does not itself trigger an unrelated delivery pass.

Per-library delivery modes can be changed in the library view. Changes apply to future scheduling decisions; queue entries already scheduled retain their existing due time. The delivery history displays the latest 50 records and allows explicit retries, with separate confirmation required for a successful prior delivery.

The arrivals view displays detected new-book events in pages of 50 and supports filters for server, library, author, genre, format, language, UTC detection date and delivery status. It does not show the initial silent baseline. Cover views and a detailed media view are not yet available.

The webhook test button sends a fixed test message to the selected destination. It resolves the global and webhook sender settings, optionally including a routed library's overrides; it does not change the Discord webhook itself. The test message does not use the template preview, and it does not create a normal arrival event.

The Discord preview uses fixed sample metadata and the same safe renderer as delivery. Title, description and footer can be saved as a named template and assigned to libraries; previewing alone neither saves nor sends a message. The variable selector lists available placeholders. Actual field availability depends on the BookOrbit version and each book's metadata. The avatar placeholder and inherited sender label do not yet reproduce a Discord webhook's original profile. Cover selection, per-field arrangement and drag-and-drop are not yet implemented in the editor.
