# Roadmap

Every task below has a concrete verification condition. Phase 6 is intentionally excluded from the initial release.

## Phase 0 – API research and foundation

- [x] Inspect the official BookOrbit API-key documentation and upstream source at a recorded revision.
- [x] Verify the REST routes needed for inventory, book details, authenticated covers, and library discovery.
- [x] Assess Socket.IO and record why it is not an MVP dependency.
- [x] Record compatibility risks and unverified runtime items in `BOOKORBIT_API.md`.
- [x] Establish architecture and mandatory development rules.

## Phase 1 – technical proof of concept

- [x] Implement an async, read-only BookOrbit client for auth, libraries, paginated book queries, detail, and cover requests.
- [x] Implement a Discord webhook client that sends an embed and optional cover attachment without leaking source credentials.
- [ ] Add a small authenticated API that executes a non-persistent connection/Discord test.
- [x] Add mock-transport tests for API headers, pagination, missing covers, Discord multipart payloads, and rate-limit errors.
- [x] Verify read-only BookOrbit authentication, library discovery, a book detail, an authenticated cover, and a Discord test message against user-supplied endpoints without retaining source data.
- [ ] Record a pinned target BookOrbit version and durable redacted fixtures for broad pagination and failure cases.

## Phase 2 – core engine

- [x] Add SQLAlchemy models and Alembic migrations for servers, libraries, books, events, scan history, and outbox rows.
- [x] Enable SQLite WAL and transaction-safe repository operations.
- [x] Implement transactional baseline reconciliation and `(server_id, bookorbit_book_id)` de-duplication.
- [x] Implement client-driven paginated source reconciliation and a per-server scan lock.
- [x] Implement the configurable recurring polling scheduler and core manual-scan trigger.
- [x] Wire the opt-in scheduler into the application runtime lifecycle after an explicit migration and encryption-key check.
- [x] Expose the existing manual-scan trigger through the authenticated administrator API/UI in Phase 4.
- [x] Implement transactional per-webhook outbox state transitions, exponential backoff, and Discord retry-hint handling.
- [x] Implement configurable metadata delay, bounded detail refresh, deadline release, and stale-send recovery.
- [x] Implement the outbound Discord delivery worker over the persistent outbox.
- [x] Add persistent per-target delivery history, status summaries, and explicit-confirmation manual retry domain controls.
- [x] Expose delivery status, history and retry controls through the authenticated administrator API/UI in Phase 4.
- [ ] Expose detailed recovery observability through the authenticated administrator API/UI.
- [x] Add SQLite- and HTTPX-simulated integration tests for restart recovery, partial scans, source outage, and Discord outage behaviour.
- [ ] Validate the same acceptance scenarios against a real BookOrbit release and a disposable Discord webhook before production use.

## Phase 3 – multi-server routing

- [x] Implement server/library/webhook/template configuration and encrypted credentials.
- [x] Implement many-to-many library-to-webhook routing and independent delivery state.
- [x] Implement configurable single, batch, and daily-summary modes.

## Phase 4 – web UI and local administration

- [ ] Verify the cover-delivery fix end-to-end using an authenticated BookOrbit cover and an explicitly authorized test webhook. Automated simulated source/Discord integration tests pass.
- [x] Fix duration template variables: keep `duration_seconds` as seconds; format `duration` as `HH:MM h`, or `MM min` when hours are zero. Verify the displayed values in the preview and delivered message.
- [x] Show a bundled sample cover in the template preview and its explicitly sent test message when covers are enabled; mark unavailable link variables in the editor.
- [x] Provide list, table and lazily loaded cover-grid views for detected arrivals, with existing filters and detail history.
- [x] Show the latest recorded library-scan result and the runtime's next scheduled scan per configured server when available.
- [x] Add authenticated, paginated library-scan history with server, library, result and UTC-date filters; omit stored error text.
- [x] Show recently detected arrivals and lazily loaded covers on the overview without including the initial baseline.
- [x] Allow configuring source timeout and TLS verification, and provide an explicit read-only metadata/cover sample check for a selected library.
- [x] Add a bounded, automatically rotated viewer for selected allowlisted operational events, with severity, source and UTC-date filters.
- [ ] Expand observability beyond the selected operational events; full application/error log coverage remains incomplete.
- [ ] Build setup, login, dashboard, server, library, webhook, history, log, settings, and template-editor views.
- [ ] Provide German and English text, responsive layout, and dark mode by default.
- [ ] Add safe redacted exports and confirmation flows for risky/manual resend operations.

### Individuelle Discord-Absenderprofile

- [x] Add independent global, webhook-specific, and library-specific sender-name and avatar-URL overrides. The global display-name default is `BookOrbit Notifier`.
- [x] Resolve each field independently in this order: library override, webhook override, global override, then Discord's original webhook configuration. A lower configuration level may explicitly inherit its parent or use the original webhook value.
- [x] Send resolved values using Discord's documented per-message `username` and `avatar_url` webhook parameters, so one Discord webhook can publish different sender profiles without changing its saved configuration.
- [x] Provide a bundled BookOrbit Notifier logo option, a custom avatar URL option, an original-webhook option, and a live Discord-message preview in the WebUI. The public asset is pinned to a repository commit; real Discord fetching still needs verification.
- [ ] Add profile-aware test messages. Validate custom avatar URLs for safe, Discord-reachable public HTTP(S) use; never rely on public reachability of the BookOrbit server or proxy source credentials through Discord.
- [ ] Do not call Discord's Modify Webhook API as part of normal delivery. A durable webhook-configuration change requires an explicit, separately confirmed administrator action.

## Phase 5 – production readiness

- [ ] Add encrypted secret storage, Argon2id sessions, CSRF/XSS protections, and security tests.
- [ ] Add consistent SQLite backups, restore validation, JSON config export, and CSV history export.
- [ ] Add Docker multi-stage build, Compose example, health check, and AMD64/ARM64 GitHub Actions release workflow.
- [ ] Complete unit/integration test matrix and operator documentation.
