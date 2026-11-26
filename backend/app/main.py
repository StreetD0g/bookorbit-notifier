"""FastAPI application entry point with an opt-in persistent worker runtime."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.poc import router as poc_router
from app.core.config import get_settings
from app.core.crypto import SecretCipher
from app.database.session import create_database_engine, create_session_factory
from app.providers.events.bookorbit.factory import EncryptedBookOrbitClientFactory
from app.queue.worker import DefaultEmbedBuilder, DiscordDeliveryWorker, EncryptedWebhookTargetResolver
from app.scanner.polling import BookOrbitPollingService
from app.scheduler.runtime import RuntimeScheduler
from app.services.metadata import MetadataRefreshService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the scheduler only after an operator explicitly enables the runtime.

    Database migrations remain an explicit deployment step. This lifecycle never
    creates tables, avoiding accidental schema changes when a container starts.
    """

    settings = get_settings()
    if not settings.runtime_enabled:
        yield
        return
    if settings.encryption_key is None:
        raise RuntimeError("An application encryption key is required when the runtime is enabled")

    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    cipher = SecretCipher(settings.encryption_key.get_secret_value())
    scheduler = RuntimeScheduler(
        session_factory,
        EncryptedBookOrbitClientFactory(session_factory, cipher),
        BookOrbitPollingService(session_factory),
        MetadataRefreshService(session_factory),
        DiscordDeliveryWorker(
            session_factory,
            EncryptedWebhookTargetResolver(session_factory, cipher),
            DefaultEmbedBuilder(session_factory),
        ),
    )
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(scheduler.run_forever(stop_event), name="bookorbit-notifier-runtime")
    app.state.runtime_scheduler = scheduler
    try:
        yield
    finally:
        stop_event.set()
        await worker_task
        engine.dispose()


app = FastAPI(
    title="BookOrbit Notifier",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(poc_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Public liveness endpoint; it intentionally reveals no configuration."""

    return {"status": "ok"}
