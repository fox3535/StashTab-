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
