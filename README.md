# BookOrbit Notifier

> [!WARNING]
> Security Notice – Vibe-Coded Project
>
> This project was developed with the assistance of artificial intelligence and has not undergone a comprehensive security review. Security vulnerabilities, programming errors, data loss, and unexpected behavior cannot be ruled out.
>
> Use this software at your own risk. Deployment in production, publicly accessible, or security-critical environments is strongly discouraged without a prior independent security review.

BookOrbit Notifier is a self-hosted, read-only service in development that detects new media in one or more [BookOrbit](https://github.com/bookorbit/bookorbit) instances and sends configurable Discord webhook notifications.

The project is independent from BookOrbit and Discord. BookOrbit's REST API is not guaranteed as a stable third-party interface; see [the compatibility research](docs/BOOKORBIT_API.md) before deployment.

## Status

Development has reached Phase 4 (Web UI). The backend persists encrypted source and destination credentials, administrator configuration and a durable per-webhook delivery queue; scheduled scans and a silent initial baseline are implemented. The administrator interface includes setup, login, routing, sender profiles, delivery history and a template editor with a Discord preview. Phase 4 remains incomplete and the project is not production-ready. See the [backend documentation](backend/README.md) for setup, limitations and verification status.

## Principles

- Read-only BookOrbit API keys with the smallest possible library scope.
- No direct BookOrbit database access, telemetry, or cloud requirement.
- Stable source IDs rather than title/ISBN matching.
- Durable detection and delivery separation to survive Discord outages.

See [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), and [development rules](AGENTS.md).
