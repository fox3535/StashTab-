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
    if startup_schema_mutation_forbidden():
        raise RuntimeError("startup schema mutation is forbidden in staging/production")
    alters = [
        "ALTER TABLE sale ADD COLUMN IF NOT EXISTS is_reconciled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS omit_graded_from_recon BOOLEAN DEFAULT FALSE",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS graded_wizard_sales_count INTEGER DEFAULT 5",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS graded_wizard_omit_diff DOUBLE PRECISION DEFAULT 20.0",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS gmail_monitor_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS gmail_address VARCHAR(100) DEFAULT ''",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS gmail_app_password VARCHAR(100) DEFAULT ''",
        "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS gmail_folder VARCHAR(100) DEFAULT 'INBOX'",
    ]
    with engine.begin() as conn:
        for stmt in alters:
            try:
                conn.execute(text(stmt))
            except Exception:
                # SQLite / non-Postgres: ignore; create_all handles fresh DBs
                pass


def startup_schema_mutation_forbidden() -> bool:
    return settings.parsed_app_env in ("staging", "production")


def bootstrap_legacy_schema() -> None:
    """Named local/test-only legacy schema bootstrap. Never used in staging/production."""
    if settings.parsed_app_env not in ("local", "test"):
        raise RuntimeError("legacy_schema_bootstrap is local/test only")
    _apply_legacy_schema()


def _apply_legacy_schema() -> None:
    from app.models import Base  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def init_db() -> None:
    if startup_schema_mutation_forbidden():
        raise RuntimeError("startup schema mutation is forbidden in staging/production")
    _apply_legacy_schema()
