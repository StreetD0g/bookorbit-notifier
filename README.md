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

## Alpha container

The development alpha is distributed as `ghcr.io/streetd0g/bookorbit-notifier:dev.alpha.1` for Linux AMD64 and ARM64. It is an early development build, not a production release. The image may require GHCR authentication depending on the package's visibility. No `latest` tag is published for alpha versions.

For the local-only Compose setup, first create the private `data/docker.env` file with an application encryption key and setup token as described in the [backend setup guide](backend/README.md). Then run:

```sh
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml run --rm notifier alembic upgrade head
docker compose -f compose.ghcr.yaml up -d
```

Open `http://127.0.0.1:18765/admin`. After initial setup, remove the setup token from `data/docker.env` and recreate the container. Preserve the encryption key separately from the database; losing it makes stored credentials unreadable. Migrations must be run explicitly before starting a new version.

Container releases are built only for tags whose commits are reachable from the explicitly approved `release` branch. The workflow runs checks before pushing a versioned image to GHCR; ordinary `dev` and `main` pushes do not publish images.

## Principles

- Read-only BookOrbit API keys with the smallest possible library scope.
- No direct BookOrbit database access or telemetry. The optional bundled Discord sender logo uses a public hosted image URL.
- Stable source IDs rather than title/ISBN matching.
- Durable detection and delivery separation to survive Discord outages.

See [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), and [development rules](AGENTS.md).
