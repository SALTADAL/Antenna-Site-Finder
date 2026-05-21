"""FastAPI entry point.

The application is structured as routers -> services -> data access:
    routers/   handle HTTP, validation, error mapping
    services/  business logic, external API wrappers
    db.py      SQLite cache + cost log
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.logging_config import configure_logging, get_logger
from app.routers import export as export_router
from app.routers import search as search_router

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup/shutdown hooks. Initializes the SQLite cache on boot."""
    init_db()
    settings = get_settings()
    logger.info(
        "Antenna Site Finder starting. mode=%s radius_default=%smi max_results=%d",
        settings.app_mode,
        settings.default_radius_miles,
        settings.max_results,
    )
    yield
    logger.info("Antenna Site Finder shutting down.")


app = FastAPI(
    title="Antenna Site Finder",
    version="0.1.0",
    description="Internal tool for Enhanced Radar field ops. Finds and ranks "
    "rooftop antenna host candidates near US airports.",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router.router)
app.include_router(export_router.router)


@app.get("/healthz")
def healthz() -> dict:
    """Liveness check used by docker-compose."""
    return {"status": "ok", "mode": settings.app_mode}


@app.get("/")
def root() -> dict:
    """Friendly root response so visiting localhost:8000 doesn't show a 404."""
    return {
        "name": "Antenna Site Finder",
        "version": "0.1.0",
        "docs": "/docs",
        "mode": settings.app_mode,
    }
