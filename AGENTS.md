# BookOrbit Notifier – Development Rules

These rules apply to every contribution.

## Delivery and branches

- Develop on `dev`. Never merge or push to `release` without the maintainer's explicit approval.
- Make small, coherent commits once a verifiable slice of work is complete.
- Do not commit credentials, local databases, backups, generated artifacts, or research checkouts.
- Keep the project independent from BookOrbit. It is not an official BookOrbit or Discord product.

## Security and privacy

- Treat BookOrbit API keys, Discord webhook URLs, sessions, encryption keys, and all values in `pre_prod_secrets.env` as secrets. Never log, return, commit, or display them.
- Use least-privilege, read-only BookOrbit API keys limited to the libraries being monitored.
- Never send a BookOrbit API key to Discord or include it in a URL.
- Encrypt persisted source and destination credentials with a separately supplied application key.
- Validate external URLs and protect administrator endpoints against authentication, CSRF, XSS, and brute-force attacks.

## Product constraints

- BookOrbit access is read-only by design. Do not call mutating BookOrbit routes.
- Book and file records are identified by source IDs, never by title, author, ISBN, or fuzzy matching.
- Persist detection independently from delivery. A Discord outage must not lose a detected event.
- An initial baseline must not create notifications unless an administrator explicitly confirms an initial import.
- Do not invent BookOrbit fields, endpoint behaviour, or socket events. Keep version-sensitive findings in `docs/BOOKORBIT_API.md`.

## Code quality

- Use explicit types, input validation, structured error handling, and comments where intent is not obvious.
- Keep BookOrbit integration behind a dedicated client/provider interface.
- Add or update tests for observable behaviour; test both success and failure paths.
- Preserve backward-compatible database migrations and use SQLite WAL mode in the application runtime.
- Prefer accessible German and English UI text and support dark mode by default.

## Verification

- Run formatting, static checks, and relevant tests before committing.
- Never test against an administrator API key when a read-only scoped key suffices.
- Mark claims that require a real BookOrbit instance as unverified until an integration test proves them.
