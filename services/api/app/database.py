from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_columns() -> None:
    """Add columns create_all won't migrate on existing Postgres tables."""
    alters = [
        "ALTER TABLE sale ADD COLUMN IF NOT EXISTS is_reconciled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS omit_graded_from_recon BOOLEAN DEFAULT FALSE",
    ]
    with engine.begin() as conn:
        for stmt in alters:
            try:
                conn.execute(text(stmt))
            except Exception:
                # SQLite / non-Postgres: ignore; create_all handles fresh DBs
                pass


def init_db() -> None:
    from app.models import Base  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
