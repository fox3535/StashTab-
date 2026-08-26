"""Identity kernel schema: shops + shop_members only."""

from app.identity_schema.migrator import apply, rollback

__all__ = ["apply", "rollback"]
