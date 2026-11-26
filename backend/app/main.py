"""FastAPI application entry point for the initial proof of concept."""

from fastapi import FastAPI

from app.api.poc import router as poc_router

app = FastAPI(title="BookOrbit Notifier", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(poc_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Public liveness endpoint; it intentionally reveals no configuration."""

    return {"status": "ok"}
