"""FastAPI application entry point with an opt-in persistent worker runtime."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from app.api.admin import router as admin_router
from app.api.poc import router as poc_router
from app.core.config import get_settings
from app.core.crypto import SecretCipher
from app.database.session import create_database_engine, create_session_factory
from app.providers.events.bookorbit.factory import EncryptedBookOrbitClientFactory
from app.queue.worker import DefaultEmbedBuilder, DiscordDeliveryWorker, EncryptedWebhookTargetResolver
from app.scanner.polling import BookOrbitPollingService
from app.scheduler.runtime import RuntimeScheduler
from app.services.event_log import EventLog
from app.services.metadata import MetadataRefreshService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the scheduler only after an operator explicitly enables the runtime.

    Database migrations remain an explicit deployment step. This lifecycle never
    creates tables, avoiding accidental schema changes when a container starts.
    """

    settings = get_settings()
    if not settings.runtime_enabled and not settings.admin_enabled:
        yield
        return
    if settings.runtime_enabled and settings.encryption_key is None:
        raise RuntimeError("An application encryption key is required when the runtime is enabled")

    try:
        event_log = EventLog(Path(settings.log_directory)) if settings.log_directory else None
    except OSError:
        logging.getLogger(__name__).warning("Operational event log is unavailable")
        event_log = None
    app.state.event_log = event_log
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    app.state.session_factory = session_factory
    if not settings.runtime_enabled:
        try:
            yield
        finally:
            if event_log is not None:
                event_log.close()
            del app.state.event_log
            del app.state.session_factory
            engine.dispose()
        return
    assert settings.encryption_key is not None
    cipher = SecretCipher(settings.encryption_key.get_secret_value())
    source_clients = EncryptedBookOrbitClientFactory(session_factory, cipher)
    scheduler = RuntimeScheduler(
        session_factory,
        source_clients,
        BookOrbitPollingService(session_factory),
        MetadataRefreshService(session_factory),
        DiscordDeliveryWorker(
            session_factory,
            EncryptedWebhookTargetResolver(session_factory, cipher),
            DefaultEmbedBuilder(session_factory),
            cover_provider=source_clients,
        ),
        event_log=event_log,
    )
    scheduler._record("runtime_started")
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(scheduler.run_forever(stop_event), name="bookorbit-notifier-runtime")
    app.state.runtime_scheduler = scheduler
    try:
        yield
    finally:
        stop_event.set()
        await worker_task
        scheduler._record("runtime_stopped")
        if event_log is not None:
            event_log.close()
        del app.state.event_log
        del app.state.session_factory
        engine.dispose()


app = FastAPI(
    title="BookOrbit Notifier",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(poc_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
_static_dir = Path(__file__).parent / "static"


class RevalidatedStaticFiles(StaticFiles):
    """Require browsers to revalidate UI assets after an application update."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/admin-assets", RevalidatedStaticFiles(directory=_static_dir), name="admin-assets")


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    """Serve the local admin shell without exposing any stored configuration."""

    if not get_settings().admin_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        _static_dir / "index.html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' https:; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Public liveness endpoint; it intentionally reveals no configuration."""

    return {"status": "ok"}
