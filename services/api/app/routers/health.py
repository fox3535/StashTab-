from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.readiness import evaluate_readiness, ping_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mimir-api"}


@router.get("/ready")
def ready() -> JSONResponse:
    db = None
    try:
        from app.database import SessionLocal

        db = SessionLocal()
        ping_database(db)
        status, body = evaluate_readiness(db)
    except Exception:
        status, body = evaluate_readiness(None)
    finally:
        if db is not None:
            db.close()
    return JSONResponse(status_code=status, content=body)
