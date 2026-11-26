# BookOrbit Notifier

> [!WARNING]
> Security Notice – Vibe-Coded Project
>
> This project was developed with the assistance of artificial intelligence and has not undergone a comprehensive security review. Security vulnerabilities, programming errors, data loss, and unexpected behavior cannot be ruled out.
>
> Use this software at your own risk. Deployment in production, publicly accessible, or security-critical environments is strongly discouraged without a prior independent security review.

BookOrbit Notifier is a planned self-hosted, read-only service that detects new media in one or more [BookOrbit](https://github.com/bookorbit/bookorbit) instances and sends configurable Discord webhook notifications.

The project is independent from BookOrbit and Discord. BookOrbit's REST API is not guaranteed as a stable third-party interface; see [the compatibility research](docs/BOOKORBIT_API.md) before deployment.

## Status

Phase 0 and the Phase-1 technical proof of concept are complete. Phase 2 is in progress: the project now has a tested SQLite/Alembic foundation, encrypted-secret primitive, silent baseline reconciliation, and a per-webhook outbox model. It does not yet persist administrator configuration or run scheduled scans, so it is not production-ready.

## Principles

- Read-only BookOrbit API keys with the smallest possible library scope.
- No direct BookOrbit database access, telemetry, or cloud requirement.
- Stable source IDs rather than title/ISBN matching.
- Later durable detection and delivery separation to survive Discord outages.

See [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), and [development rules](AGENTS.md).
