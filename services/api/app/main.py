from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.auth.identity import log_dev_identity_bypass_state
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
    init_db()
    log_dev_identity_bypass_state()
    static_root = Path(__file__).resolve().parent / "static"
    (static_root / "barcodes").mkdir(parents=True, exist_ok=True)
    (static_root / "scraped_thumbnails").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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
if settings.notifications_backend_enabled:
    app.include_router(notifications.router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
