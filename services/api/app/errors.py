"""HTTP-safe application errors that must not leak schema or secrets."""

from __future__ import annotations


class FeatureNotReadyError(RuntimeError):
    def __init__(self, feature: str, message: str | None = None) -> None:
        self.feature = feature
        self.message = message or "This operation is not enabled in this environment."
        super().__init__(self.message)


def is_missing_relation(exc: BaseException) -> bool:
    orig = getattr(exc, "orig", None)
    if getattr(orig, "pgcode", None) == "42P01":
        return True
    text = str(exc).lower()
    return "no such table" in text or "undefinedtable" in text


def is_insufficient_privilege(exc: BaseException) -> bool:
    """PostgreSQL privilege denial (SQLSTATE 42501). SQLAlchemy 2.x
    surfaces psycopg2's InsufficientPrivilege as a wrapped OperationalError,
    so classify by pgcode; the DBAPI class is a secondary signal."""
    orig = getattr(exc, "orig", None)
    if getattr(orig, "pgcode", None) == "42501":
        return True
    if orig is not None and type(orig).__name__ == "InsufficientPrivilege":
        return True
    return "insufficient privilege" in str(exc).lower()
