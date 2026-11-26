# Roadmap

Every task below has a concrete verification condition. Phase 6 is intentionally excluded from the initial release.

## Phase 0 – API research and foundation

- [x] Inspect the official BookOrbit API-key documentation and upstream source at a recorded revision.
- [x] Verify the REST routes needed for inventory, book details, authenticated covers, and library discovery.
- [x] Assess Socket.IO and record why it is not an MVP dependency.
- [x] Record compatibility risks and unverified runtime items in `BOOKORBIT_API.md`.
- [x] Establish architecture and mandatory development rules.

## Phase 1 – technical proof of concept

- [ ] Implement an async, read-only BookOrbit client for auth, libraries, paginated book queries, detail, and cover requests.
- [ ] Implement a Discord webhook client that sends an embed and optional cover attachment without leaking source credentials.
- [ ] Add a small authenticated API that executes a non-persistent connection/Discord test.
- [ ] Add mock-transport tests for API headers, pagination, missing covers, Discord multipart payloads, and rate-limit errors.
- [ ] Verify the POC with a real BookOrbit instance and a disposable Discord webhook; record the target version and fixtures.

## Phase 2 – core engine

- [ ] Add SQLAlchemy models and Alembic migrations for servers, libraries, books, events, scan history, and outbox rows.
- [ ] Enable SQLite WAL and transaction-safe repository operations.
- [ ] Implement baseline scan, periodic scan lock, paginated reconciliation, and `(server_id, bookorbit_book_id)` de-duplication.
- [ ] Implement metadata delay, retry state machine, per-webhook outbox retries, and Discord 429 handling.
- [ ] Add integration tests for restart, partial scan, source outage, and Discord outage behaviour.

## Phase 3 – multi-server routing

- [ ] Implement server/library/webhook/template configuration and encrypted credentials.
- [ ] Implement many-to-many library-to-webhook routing and independent delivery state.
- [ ] Implement configurable single, batch, and daily-summary modes.

## Phase 4 – web UI and local administration

- [ ] Build setup, login, dashboard, server, library, webhook, history, log, settings, and template-editor views.
- [ ] Provide German and English text, responsive layout, and dark mode by default.
- [ ] Add safe redacted exports and confirmation flows for risky/manual resend operations.

## Phase 5 – production readiness

- [ ] Add encrypted secret storage, Argon2id sessions, CSRF/XSS protections, and security tests.
- [ ] Add consistent SQLite backups, restore validation, JSON config export, and CSV history export.
- [ ] Add Docker multi-stage build, Compose example, health check, and AMD64/ARM64 GitHub Actions release workflow.
- [ ] Complete unit/integration test matrix and operator documentation.
