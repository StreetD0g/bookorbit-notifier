# BookOrbit Notifier

BookOrbit Notifier is a planned self-hosted, read-only service that detects new media in one or more [BookOrbit](https://github.com/bookorbit/bookorbit) instances and sends configurable Discord webhook notifications.

The project is independent from BookOrbit and Discord. BookOrbit's REST API is not guaranteed as a stable third-party interface; see [the compatibility research](docs/BOOKORBIT_API.md) before deployment.

## Status

Phase 0 is complete. The Phase-1 technical proof of concept provides a tested asynchronous BookOrbit REST client and Discord webhook transport. It does not yet persist configuration, scan state, or delivery work, so it is not production-ready.

## Principles

- Read-only BookOrbit API keys with the smallest possible library scope.
- No direct BookOrbit database access, telemetry, or cloud requirement.
- Stable source IDs rather than title/ISBN matching.
- Later durable detection and delivery separation to survive Discord outages.

See [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), and [development rules](AGENTS.md).
