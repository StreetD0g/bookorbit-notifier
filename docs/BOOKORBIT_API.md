# BookOrbit API research

**Research date:** 26 November 2026  
**Upstream inspected:** [`bookorbit/bookorbit`](https://github.com/bookorbit/bookorbit), commit `f7a2a5df406ac913b5fc6603c0b2465ec5356f98` (main at research time).  
**Evidence:** upstream `docs/API_KEYS.md`, server controllers/services, shared TypeScript types, the official client source, and a redacted read-only probe against a user-supplied BookOrbit instance on 26 November 2026.

## Compatibility position

BookOrbit's README states that its API evolves alongside official clients and is **not a stable public integration surface**. This notifier must therefore:

- use a narrow, read-only compatibility layer;
- test a server before it is activated;
- surface the connected BookOrbit version where available;
- retain polling as the supported detection mechanism; and
- make no compatibility promise without testing a released BookOrbit version.

The application exposes OpenAPI only when the BookOrbit server is started with `SWAGGER_ENABLED=true`, at `/api/docs` and `/api/docs-json`; production deployments may not expose it.

## Authentication and authorization

Use either header below on every REST request. Query-string keys are deliberately ignored upstream.

```http
Authorization: Bearer bok_...
X-Api-Key: bok_...
```

API keys are per-user, are hashed upstream, can be **Read** only, can be restricted to particular libraries, and may expire. `GET /api/v1/auth/me` is the documented connection and scope check; its response indicates `authenticationMethod: "api_key"` and the effective permissions.

For the notifier, create one dedicated, read-only key with no extra permissions and only the monitored libraries. A key lacks access immediately if it is revoked, expired, disabled server-wide, or its owner loses the necessary permission. Invalid keys are rate-limited after 30 unknown/invalid keys per address per minute.

## Verified REST routes for the MVP

All controller paths below are prefixed by `/api/v1`.

| Route | Read-key safe | Purpose in notifier | Verified request/response facts |
| --- | --- | --- | --- |
| `GET /auth/me` | Yes | Connection and key-scope test | Documented API-key authentication check. |
| `GET /health` | Public | Optional reachability check | Nest Terminus health result; do not treat it as authentication success. |
| `GET /libraries` | Yes (GET) | Discover accessible libraries | Returns the user's accessible library records. `Library` includes numeric `id`, `name`, `allowedFormats`, `organizationMode`, `addedAtSource`, timestamps, and may include `bookCount`. |
| `POST /books/query` | Yes (`@KeyReadSafe`) | Paginated global inventory and full reconciliation | Body accepts `sort`, `pagination`, optional `q`, `filter`, `collapseSeries`, and `collapseLinked`. Response is `{ items, total, page, size, bookTotal? }`. Page is zero-based; size is 1–200. |
| `POST /libraries/{libraryId}/books` | Yes (`@KeyReadSafe`) | Library-scoped inventory and polling | Same query/response model as `/books/query`; server verifies viewer access to the library. |
| `GET /books/{bookId}` | Yes (GET) | Refresh a detected book before publication | Returns a `BookDetail` with numeric `id`, numeric `libraryId`, `libraryName`, `addedAt`, `updatedAt`, metadata, `files`, and cover state. |
| `GET /books/{bookId}/cover` | Yes (GET) | Download a cover through authenticated access | Streams the source cover. Optional `medium=ebook|audio`, `strict=true|false`, `size=display`, and cache token `t` are implemented. Missing cover returns 404. |
| `GET /books/{bookId}/thumbnail` | Yes (GET) | Smaller cover fallback | Streams JPEG thumbnail. Optional `medium`, `strict`, and `t`; missing thumbnail returns 404. |
| `GET /books/search?q=…&limit=…` | Yes (GET) | Not used for detection | Search only: `q` is required (1–500 chars), `limit` is 1–20. It is not a paginated inventory endpoint. |

The concept's proposed `GET /api/v1/books/search`, `GET /api/v1/books/{id}`, `/cover`, and `/thumbnail` do exist. The proposed `POST /api/v1/books/query` exists. The library-scoped `POST /api/v1/libraries/{id}/books` is preferred whenever a library is monitored.

## Query contract and new-arrival detection

The verified minimal query body for a stable full reconciliation is:

```json
{
  "sort": [{"field": "addedAt", "dir": "desc"}],
  "pagination": {"page": 0, "size": 200}
}
```

Supported source sort fields include `addedAt`, `updatedAt`, `title`, `author`, `publishedDate`, `format`, `fileSize`, `language`, and others. `addedAt` is suitable to prioritize work but **not** to prove novelty: a library's configured `addedAtSource` can be `imported`, `file_modified`, or `file_created`. The notifier must page the complete result set on its periodic reconciliation and use the durable `(server_id, bookorbit_book_id)` pair as its identity.

Each `BookCard` returned in `items` has at least a numeric `id`; the current source also exposes `libraryId`, `title`, `authors`, `files`, `addedAt`, `updatedAt`, `hasCover`, and `coverVersion`. A `BookDetail` adds longer metadata such as description, publisher, ISBN, narrators, duration in `audioMetadata`, and full file records. Fields are nullable and must be treated as optional.

BookOrbit represents a logical book and exposes an array of attached files. Therefore the notifier should emit a `BOOK_ADDED` event per newly observed **book ID**, not per file. File additions to an existing ID remain out of scope for the MVP.

### Fields available for notification templates

The pinned upstream `packages/types/src/book.ts` describes the following `BookDetail` fields: `title`, `subtitle`, `description`, `authors[].name`, `seriesName`, `seriesIndex`, `genres`, `tags`, `language`, `publisher`, `publishedDate`, `publishedYear`, `pageCount`, `isbn10`, `isbn13`, `rating`, `addedAt`, `updatedAt`, `files[].format`, `collections[].name`, and `audioMetadata` with `narrators[].name`, `durationSeconds`, and `abridged`. `editionName` and `originalPublishedYear` are optional on newer servers. Each field may be absent or null; duration is in seconds. Book cards instead expose narrator names directly as strings. Account-specific notes, reading progress, filesystem paths, and provider identifiers are deliberately excluded from templates.

The notifier exposes corresponding snake-case variables, including `{{published_year}}`, `{{page_count}}`, `{{narrators}}`, and `{{duration_seconds}}`. Missing values render empty. Existing compatibility placeholders `{{age_rating}}` and `{{content_warnings}}` are not confirmed in the inspected `BookDetail` type and must not be assumed present. `{{book_url}}` and `{{cover_url}}` remain empty until safe, verified link handling is implemented. The prior real-instance probe established that detail retrieval works; the field mapping above is source-verified, not yet verified field-by-field against a pinned real release.

## Covers and direct links

Covers require the same authenticated request as other book routes. The notifier must download and validate the bytes itself, then attach them to the Discord webhook and reference `attachment://…`; it must never embed a BookOrbit API key in a Discord URL. The public BookOrbit base URL, if configured, is only for a user-facing direct book link and is never used for API authentication.

The exact web-UI deep-link format is not declared as a public contract in the inspected server source. It remains **open** and must be verified against a real target release before being enabled by default.

## Socket.IO assessment

The upstream source contains an authenticated Socket.IO `/scan` namespace. The documented API-key guide says a key may be passed as `auth.token` during the Socket.IO handshake. A client joins an accessible library with `subscribe:library`; the server emits `scan:books:added` to that library room. At the inspected commit its event shape is:

```ts
{ libraryId: number, books: BookCard[] }
```

This is useful evidence that real-time detection is technically possible, but BookOrbit does not document this namespace/event as a stable third-party integration contract. It is not part of the MVP and must not be required for delivery. A future opt-in provider may use it only with polling reconciliation as a fallback and with version-specific integration tests.

## Limitations and items requiring a real server

- No public release matrix or guaranteed third-party API compatibility was found.
- A read-only live probe authenticated successfully with an API key, discovered seven accessible libraries, queried one paginated library inventory, retrieved one book detail record, and downloaded one authenticated cover. The probe intentionally did not record account, library, or media values.
- The exact error envelope, pagination behaviour under concurrent scans, rate limits for normal valid requests, and all runtime response payloads still need fixture-backed integration tests against a pinned real server version.
- Library discovery, read-key scoping, cover retrieval, and a first query are now live-validated; broad pagination and failure cases still require target-version validation during server setup.
- Direct-book UI URLs are unverified and optional.
- Socket.IO event stability is unverified; REST polling is the production path.

## Sources

- [BookOrbit API keys guide](https://github.com/bookorbit/bookorbit/blob/main/docs/API_KEYS.md)
- [BookOrbit API compatibility notice](https://github.com/bookorbit/bookorbit/blob/main/README.md#-api-compatibility)
- [Book controller](https://github.com/bookorbit/bookorbit/blob/main/server/src/modules/book/book.controller.ts)
- [Book and audio response types at the inspected revision](https://github.com/bookorbit/bookorbit/blob/f7a2a5df406ac913b5fc6603c0b2465ec5356f98/packages/types/src/book.ts)
- [Narrator response type at the inspected revision](https://github.com/bookorbit/bookorbit/blob/f7a2a5df406ac913b5fc6603c0b2465ec5356f98/packages/types/src/audiobook.ts)
- [Library controller](https://github.com/bookorbit/bookorbit/blob/main/server/src/modules/library/library.controller.ts)
- [Scan gateway](https://github.com/bookorbit/bookorbit/blob/main/server/src/modules/scanner/scan.gateway.ts)
