# Architecture

## Scope and principles

BookOrbit Notifier is a self-hosted, read-only companion service. It reads accessible BookOrbit data, records detection state in its own SQLite database, and delivers independently persisted notification work to Discord. It never reads the BookOrbit database or changes BookOrbit data.

```text
BookOrbit REST API
       │  (scoped read-only key)
       ▼
BookOrbit client → polling provider → detection transaction → SQLite events/outbox
                                                           │
                                                           ▼
                                           metadata refresh / cover download
                                                           │
                                                           ▼
                                            Discord webhook delivery worker
```

The critical boundary is the outbox: source detection commits a book/event and one delivery record per webhook in one SQLite transaction. Delivery happens later. A Discord outage cannot discard a detected book, and a retry for one webhook cannot resend a completed delivery to another webhook.

## Components

| Component | Responsibility |
| --- | --- |
| `providers/events/bookorbit` | Thin, version-aware HTTP client and REST polling provider. It owns no notification logic. |
| `scanner` | Runs one scan per server at a time, establishes baselines, pages inventories, and emits durable domain events. |
| `services` | Orchestrates connection tests, metadata waiting, routing, statistics, backups, and admin workflows. |
| `queue` | Claims durable delivery work, observes retry schedules and Discord rate limits, and records one status per webhook target. |
| `providers/notifications/discord` | Builds the Discord transport request only. It can send a multipart cover attachment without exposing source credentials. |
| `database` | SQLAlchemy models, Alembic migrations, SQLite WAL setup, repository transactions, and encrypted secret columns. |
| `api` | Authenticated administrative REST API plus public `/health`; schemas never expose stored secret material. |
| `frontend` | React/Vite admin UI served from the same container in production. |

## Data and identity

`books` has a unique constraint on `(server_id, bookorbit_book_id)`. `events` refers to a book and carries an extensible event type (`BOOK_ADDED` first). `notification_queue` has one row per `(event_id, webhook_id)` and records status, attempt count, retry time, error, and Discord message ID.

The first successful scan creates a baseline of IDs and does not enqueue events. An explicit, confirmed initial import is the sole exception. Subsequent scans insert unknown IDs, enqueue metadata waiting, and retain previously known records even after a partial/failed scan. Full reconciliation is the safety net; `addedAt` influences ordering only.

## Security boundary

- API keys and webhook URLs are encrypted at rest using an application-supplied encryption key not stored in SQLite.
- Secrets are redacted in logs and omitted from normal responses and exports.
- The service accepts only administrator-configured source and webhook URLs and validates schemes, host policy, redirects, and response limits before network use.
- Local admin access uses Argon2id password hashes, secure sessions, CSRF protection, and login rate limiting.
- Reverse-proxy deployment is supported through an explicit trusted-proxy configuration.

## Runtime and recovery

One container contains the API, scheduler, queue worker, and built frontend. SQLite lives in `/data`, runs with WAL mode, and is backed up using SQLite-consistent operations. On restart the scanner resumes from persisted state and the worker continues eligible queue rows. Duplicate delivery is minimized by durable state but cannot be mathematically guaranteed after an ambiguous network failure following Discord acceptance.

## Version compatibility

BookOrbit REST interfaces are not a stable third-party contract. The BookOrbit client is isolated so compatibility checks, response adaptation, and regression fixtures can change without leaking upstream details into the domain model. The connection test must reject inaccessible/unsupported instances before monitoring begins.
