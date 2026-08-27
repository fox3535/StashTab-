# Correction pass after slice-01 implementation review

One pass. No extra review loop.

## Applied

1. Scorer-failure handling re-raises HTTP errors from the feature gate instead of recording them as abstentions.
2. Concurrent identical intake serializes the in-process submit path, then relies on the unique constraint as the second line of defense. After commit or unique conflict the session is expired and the stored row is re-read.
3. HTTP tests open a session per request so concurrent calls do not share one SQLAlchemy session.
4. PostgreSQL grant proof seeds shops through the admin connection and does not assume the API role cannot insert identity rows.
5. Concurrent HTTP tests use a file-backed SQLite database so threads do not share one in-memory connection.

## Not changed

- Staging and production stay disabled.
- JustTCG, TCGCSV, and Pokémon TCG HTTP stay unused.
- Accepted identity still does not write inventory.
- Implementation is accepted locally and remains unmerged, undeployed,
  and feature-off until a later unlock.
