from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.config import settings
from app.database import init_db
from app.errors import FeatureNotReadyError, is_insufficient_privilege, is_missing_relation
from app.auth.identity import log_dev_identity_bypass_state
from app.card_resolution.router import router as card_resolution_router
from app.routers import (
    admin,
    health,
    inventory,
    notifications,
    reports,
    sales,
    shops,
    shows,
    sync,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.database import startup_schema_mutation_forbidden

    if not startup_schema_mutation_forbidden():
        init_db()
    log_dev_identity_bypass_state()
    static_root = Path(__file__).resolve().parent / "static"
    (static_root / "barcodes").mkdir(parents=True, exist_ok=True)
    (static_root / "scraped_thumbnails").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(FeatureNotReadyError)
async def feature_not_ready_handler(_request, exc: FeatureNotReadyError):
    return JSONResponse(
        status_code=503,
        content={
            "error": "FEATURE_NOT_READY",
            "feature": exc.feature,
            "message": exc.message,
        },
    )


def _controlled_unavailable_response() -> JSONResponse:
    # Generic body only — never leak SQL text, role names, or stack traces.
    return JSONResponse(
        status_code=503,
        content={
            "error": "FEATURE_NOT_READY",
            "feature": "inventory",
            "message": "This operation is not enabled in this environment.",
        },
    )


@app.exception_handler(OperationalError)
async def operational_error_handler(_request, exc: OperationalError):
    """AMENDMENT-1.3.0 §8: after cutover the runtime keeps column-scoped
    grants; any privilege denial (SQLSTATE 42501, surfaced by SQLAlchemy
    2.x as a wrapped OperationalError) becomes a controlled 503, never a
    raw 500 with database details. Other operational errors keep the
    generic path."""
    if is_insufficient_privilege(exc):
        return _controlled_unavailable_response()
    raise exc


@app.exception_handler(ProgrammingError)
async def programming_error_handler(_request, exc: ProgrammingError):
    """AMENDMENT-1.3.0 §8: undefined relations (tables not provisioned in
    this environment) map to controlled 503. Other programming errors keep
    the generic 500 path."""
    if is_missing_relation(exc):
        return _controlled_unavailable_response()
    raise exc


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(shops.router, prefix=settings.api_prefix)
app.include_router(inventory.router, prefix=settings.api_prefix)
app.include_router(sales.router, prefix=settings.api_prefix)
app.include_router(sync.router, prefix=settings.api_prefix)
app.include_router(shows.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(card_resolution_router, prefix=settings.api_prefix)
if settings.notifications_backend_enabled:
    app.include_router(notifications.router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
