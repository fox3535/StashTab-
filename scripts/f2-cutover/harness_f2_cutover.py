"""Disposable PostgreSQL 16 proof harness for the F2 generation-1 cutover packet.

What this file is
-----------------
A throwaway, local-only proof that ``scripts/f2-cutover/sql`` behaves exactly as
``docs/inventory-truth-v1/RUNBOOK-F2-CUTOVER-GEN1.md`` claims when it runs
against the ACCEPTED schema produced by the reviewed migrators. It is not part
of the operator command set and it is not collected by ``pytest tests -q`` in
``services/api``, so it cannot affect the backend CI jobs.

What this file never does
-------------------------
It never contacts staging, production, Neon, Railway or Clerk. It never creates
a real credential, never runs a migrator against anything but a container that
is destroyed at teardown, never issues DELETE or TRUNCATE, and never performs a
successful receive. Every HTTP probe below is required to fail closed: a 2xx
from the receive endpoint fails the harness.

The packet's "no seed" rule is a rule about the target database, and the target
here is throwaway. ``Pg16.provision`` does insert two ``shops`` rows and two
``shop_members`` rows into its own container, because R6 asserts the D-045
decision 2 identity baseline of exactly ``shops = 2`` / ``shop_members = 2`` and
there is no other way to evaluate it. Smoke Shop B carries its real pinned id so
the guard, the WHERE clauses and the HTTP probes are exercised against the value
the operator will actually type; the second shop is a control tenant that
proves the ``complete`` transition does not open anyone else's gate. Both rows
are destroyed with the container. Nothing is seeded into staging, and no
operator command in ``sql/`` inserts identity data.

The two negative fixtures ``_inject_r1_variance`` and
``_inject_overlay_reverse_violation`` are likewise harness-only, run only
against DB_NEG, and are INSERTs -- even a negative fixture respects the
append-only evidence rule.

Credential shape
----------------
No connection URL is built anywhere. psql is driven through PGHOST, PGPORT,
PGDATABASE, PGUSER and PGPASSWORD inside the container, which is the same
mechanism the runbook prescribes for the operator, so no URL can leak into a
command line, a log, or this file's output. The passwords here are fixed
literals for a container that no longer exists when the test ends; they are not
secrets and nothing is read from the environment or from disk.

Required behaviors proved (packet deliverable 7)
------------------------------------------------
H1  wrong database, wrong role and wrong shop all fail closed
H2  a duplicate generation fails closed
H3  ``locking`` keeps receive unavailable
H4  the R1-R7 zero checks are deterministic
H5  a timeout, an error and a mismatch cannot pass
H6  the ``complete`` transition affects only Smoke Shop B
H7  break-glass returns only that row to ``locking``
H8  no evidence rows are deleted
H9  rerun behavior is explicit and safe

Run it (twice, on fresh disposable databases, is built in):

    python -m pytest scripts/f2-cutover/harness_f2_cutover.py -q
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid as uuid_mod
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
SQL_DIR = Path(__file__).resolve().parent / "sql"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

DOCKER_MISSING = shutil.which("docker") is None

pytestmark = pytest.mark.skipif(DOCKER_MISSING, reason="docker CLI unavailable")

IMAGE = "postgres:16"
CONTAINER_SQL_DIR = "/f2-cutover-sql"
PGHOST = "127.0.0.1"
PGPORT = "5432"

# Fixed literals for a container destroyed at teardown. Not credentials.
SUPERUSER = "postgres"
SUPERUSER_PASSWORD = "stashtab"
ROLE_PASSWORDS = {
    "stashtab_migrator": "mig",
    "stashtab_api": "api",
    "stashtab_worker": "wrk",
    "stashtab_readonly": "ro",
}

WRITE_ROLE = "stashtab_migrator"
READ_ROLE = "stashtab_api"
WORKER_ROLE = "stashtab_worker"
READONLY_ROLE = "stashtab_readonly"

DB_MAIN = "f2_cutover"
DB_NEG = "f2_cutover_neg"
DB_WRONG = "f2_cutover_wrong"

# D-045 decision 2. Pinned once, here, and supplied to psql twice per
# invocation (cutover_shop_id and pinned_shop_id) so guard G1b double-enters it.
PINNED_SHOP_ID = "798d40f4-0832-46c4-991b-050e1310f6c4"
CONTROL_SHOP_ID = "3f2a9c14-6b7d-4e88-9a01-2c3d4e5f6071"
ABSENT_SHOP_ID = "9e8d7c6b-5a49-4837-8625-1403d2c1b0af"

PINNED_OWNER = "owner-b"
CONTROL_OWNER = "owner-a"

# D-045 decision 5: reserved, and never used by this packet.
RESERVED_KEY = "F2-CUT-GEN1-0001"

RECEIVE_URL = "/api/v1/admin/inventory/receive"
READY_URL = "/api/v1/ready"

RECON_TIMEOUT_MS = "15000"
LOCK_TIMEOUT_MS = "2000"
VERIFY_TIMEOUT_MS = "15000"
BREAK_GLASS_TIMEOUT_MS = "15000"

GATE_TOKENS = (
    "R1-zero",
    "overlay-deltas-are-zero",
    "one-stock-row-per-sku",
    "R2-zero",
    "R3-zero",
    "R4-zero",
    "R5a-unchanged",
    "R5c-envelope-empty",
    "R6-zero",
    "R7a-zero",
    "R7b-zero",
    "R7c-zero",
    "R7d-zero",
    "R7e-zero",
)

GATE_COLUMNS = (
    "r1_result",
    "r1c_overlay_hygiene",
    "r1d_snapshot_key_discipline",
    "r1_snapshot_rows_examined",
    "r1_event_rows_examined",
    "r2_result",
    "r2_rows_examined",
    "r3_result",
    "r3b_replay_rows_added",
    "r4_result",
    "r5a_result",
    "r5c_result",
    "r6_result",
    "r7a_result",
    "r7b_result",
    "r7c_result",
    "r7d_result",
    "r7e_result",
)

CATALOG_RELATIONS_SQL = """
SELECT c.relname
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public'
   AND c.relkind = 'r'
 ORDER BY c.relname
"""


def _ensure_pandas_importable() -> None:
    """Harness-only shim, same rationale as services/api/tests/test_f2_receive_pg.py."""
    try:
        import pandas  # noqa: F401

        return
    except ImportError:
        pass
    import types

    def _unavailable(*_args, **_kwargs):
        raise RuntimeError("pandas unavailable in this test environment")

    stub = types.ModuleType("pandas")
    stub.DataFrame = object
    stub.Series = object
    stub.read_csv = _unavailable
    stub.to_datetime = _unavailable
    sys.modules.setdefault("pandas", stub)


_ensure_pandas_importable()


def _free_port() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return str(sock.getsockname()[1])


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _admin_url(port: str, db: str = "postgres") -> str:
    """Superuser URL for container bootstrap only.

    This is the one place a URL exists, it is built at call time, it is never
    written to a file, and it never carries a real credential. The packet
    itself is driven exclusively through libpq environment variables.
    """
    return f"postgresql://{SUPERUSER}:{SUPERUSER_PASSWORD}@127.0.0.1:{port}/{db}"


def _role_url(role: str, port: str, db: str) -> str:
    return f"postgresql://{role}:{ROLE_PASSWORDS[role]}@127.0.0.1:{port}/{db}"


_SEPARATOR = re.compile(r"^-+(?:\+-+)*$")


def _aligned_tables(stdout: str) -> list[tuple[list[str], list[list[str]]]]:
    """Parse psql aligned output into (headers, rows) pairs."""
    tables: list[tuple[list[str], list[list[str]]]] = []
    lines = stdout.splitlines()
    for index in range(1, len(lines)):
        if not _SEPARATOR.match(lines[index].strip()):
            continue
        header_line = lines[index - 1]
        if header_line.lstrip().startswith("-"):
            continue  # an \echo rule, not a result header
        headers = [cell.strip() for cell in header_line.split("|")]
        rows: list[list[str]] = []
        cursor = index + 1
        while cursor < len(lines):
            stripped = lines[cursor].strip()
            if not stripped or stripped.startswith("("):
                break
            rows.append([cell.strip() for cell in lines[cursor].split("|")])
            cursor += 1
        tables.append((headers, rows))
    return tables


def _first_value(stdout: str, column: str) -> str:
    for headers, rows in _aligned_tables(stdout):
        if column in headers and rows:
            return rows[0][headers.index(column)]
    raise AssertionError(f"column {column!r} absent from psql output:\n{stdout}")


class PsqlResult:
    """One psql invocation: exit status plus both streams, verbatim."""

    def __init__(self, returncode: int, stdout: str, stderr: str, label: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.label = label

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def failed_with(self, marker: str) -> bool:
        """True when psql stopped and named this exact invariant."""
        return not self.ok and marker in self.stderr

    def __str__(self) -> str:
        return (
            f"\n=== {self.label} exit={self.returncode} ===\n"
            f"--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"
        )

    __repr__ = __str__


class Pg16:
    """One disposable postgres:16 container holding three throwaway databases."""

    def __init__(self, container: str, port: str):
        self.container = container
        self.port = port
        self._engines: dict[tuple[str, str], object] = {}
        self._provisioned: set[str] = set()
        self._created: set[str] = set()

    # --- engine plumbing ---------------------------------------------------

    def engine(self, db: str, role: str = SUPERUSER):
        from sqlalchemy import create_engine

        key = (db, role)
        if key not in self._engines:
            url = _admin_url(self.port, db) if role == SUPERUSER else _role_url(role, self.port, db)
            self._engines[key] = create_engine(url, pool_pre_ping=True)
        return self._engines[key]

    def query(self, db: str, sql: str, params: dict | None = None, role: str = SUPERUSER):
        from sqlalchemy import text

        with self.engine(db, role).connect() as conn:
            return conn.execute(text(sql), params or {}).fetchall()

    def scalar(self, db: str, sql: str, params: dict | None = None, role: str = SUPERUSER):
        rows = self.query(db, sql, params, role)
        return rows[0][0] if rows else None

    def catalog_counts(self, db: str) -> dict[str, int]:
        """Every public table and its row count. Proves nothing was deleted.

        Counted with one plain query per relation rather than with the
        query_to_xml walk that 08-break-glass-locking.sql uses, so the harness
        cross-checks the packet's own mechanism instead of sharing its bugs.
        """
        relations = [str(row[0]) for row in self.query(db, CATALOG_RELATIONS_SQL)]
        return {
            rel: int(self.scalar(db, f'SELECT count(*) FROM public."{rel}"'))
            for rel in relations
        }

    def dispose(self) -> None:
        for engine in self._engines.values():
            engine.dispose()
        self._engines.clear()

    # --- psql plumbing -----------------------------------------------------

    def psql(
        self,
        db: str,
        role: str,
        file: str | None = None,
        variables: dict[str, str] | None = None,
        sql: str | None = None,
    ) -> PsqlResult:
        """Run one packet file (or one statement) as one role against one database.

        Credentials travel as libpq environment variables inside the container.
        Packet variables are not secrets: they are the pinned shop id, the
        generation, role names, digests and timeouts.
        """
        password = SUPERUSER_PASSWORD if role == SUPERUSER else ROLE_PASSWORDS[role]
        cmd = [
            "docker", "exec",
            "-e", f"PGHOST={PGHOST}",
            "-e", f"PGPORT={PGPORT}",
            "-e", f"PGDATABASE={db}",
            "-e", f"PGUSER={role}",
            "-e", f"PGPASSWORD={password}",
            self.container,
            "psql", "-X", "-v", "ON_ERROR_STOP=1",
        ]
        for name, value in (variables or {}).items():
            cmd += ["-v", f"{name}={value}"]
        if file is not None:
            cmd += ["-f", f"{CONTAINER_SQL_DIR}/{file}"]
            label = f"{db}/{role}/{file}"
        else:
            cmd += ["-c", sql or ""]
            label = f"{db}/{role}/-c"
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return PsqlResult(proc.returncode, proc.stdout, proc.stderr, label)

    # --- database lifecycle ------------------------------------------------

    def create_database(self, db: str) -> None:
        """Create one throwaway database and set its schema-level privileges.

        Schema privileges are per-database, so they are applied here rather than
        once on the bootstrap connection. PUBLIC loses CREATE, only the
        migrator role keeps it, and the three runtime roles get USAGE alone.
        """
        if db in self._created:
            return
        from sqlalchemy import text

        with self.engine("postgres").connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(text(f"CREATE DATABASE {db}"))
            conn.execute(
                text(
                    f"GRANT CONNECT ON DATABASE {db} TO "
                    "stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly"
                )
            )
        with self.engine(db).connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(
                text(
                    "GRANT USAGE ON SCHEMA public TO "
                    "stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly"
                )
            )
            conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            conn.execute(text("GRANT CREATE ON SCHEMA public TO stashtab_migrator"))
            conn.execute(
                text(
                    "REVOKE CREATE ON SCHEMA public FROM "
                    "stashtab_api, stashtab_worker, stashtab_readonly"
                )
            )
        self._created.add(db)

    def provision(self, db: str) -> None:
        """Build the accepted schema in one database with the reviewed migrators.

        Ordering is forced by identity_schema.migrator.apply(), whose strict
        post-verification rejects any extra relation, so identity goes first
        and the notification slice goes last.
        """
        if db in self._provisioned:
            return
        from sqlalchemy import text

        from app.identity_schema.migrator import apply as apply_identity
        from app.inventory_live_schema.migrator import apply_f2_receive, apply_rehearsal
        from app.notifications_truth.migrator import apply_notification_schema

        self.create_database(db)
        mig = self.engine(db, WRITE_ROLE)
        apply_identity(mig)
        with mig.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO shops (id, name, slug, created_at, updated_at) VALUES "
                    "(:pinned, 'Smoke Shop B', 'smoke-shop-b', NOW(), NOW()), "
                    "(:control, 'Harness Control Shop', 'harness-control', NOW(), NOW())"
                ),
                {"pinned": PINNED_SHOP_ID, "control": CONTROL_SHOP_ID},
            )
            conn.execute(
                text(
                    "INSERT INTO shop_members "
                    "(id, shop_id, clerk_user_id, role, created_at, updated_at) VALUES "
                    "('mem-b', :pinned, :owner_b, 'owner', NOW(), NOW()), "
                    "('mem-a', :control, :owner_a, 'owner', NOW(), NOW())"
                ),
                {"pinned": PINNED_SHOP_ID, "control": CONTROL_SHOP_ID,
                 "owner_b": PINNED_OWNER, "owner_a": CONTROL_OWNER},
            )
        apply_rehearsal(mig)
        applied = apply_f2_receive(mig)
        assert applied["indexes"] == ["uq_purchase_record_shop_client_key"], applied
        assert applied["grants"], applied

        previous_migrator = os.environ.get("STASHTAB_NOTIFICATION_MIGRATOR_ROLE")
        previous_runtime = os.environ.get("STASHTAB_NOTIFICATION_RUNTIME_ROLE")
        os.environ["STASHTAB_NOTIFICATION_MIGRATOR_ROLE"] = WRITE_ROLE
        os.environ["STASHTAB_NOTIFICATION_RUNTIME_ROLE"] = READ_ROLE
        try:
            apply_notification_schema(mig)
        finally:
            for name, previous in (
                ("STASHTAB_NOTIFICATION_MIGRATOR_ROLE", previous_migrator),
                ("STASHTAB_NOTIFICATION_RUNTIME_ROLE", previous_runtime),
            ):
                if previous is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous
        self._provisioned.add(db)


def _vars(db: str, **overrides) -> dict[str, str]:
    """The guard variables every packet file requires, for one database."""
    values = {
        "cutover_shop_id": PINNED_SHOP_ID,
        "pinned_shop_id": PINNED_SHOP_ID,
        "cutover_generation": "1",
        "write_role": WRITE_ROLE,
        "read_role": READ_ROLE,
        "expected_database": db,
        "expected_role": WRITE_ROLE,
        "expected_shops": "2",
        "expected_shop_members": "2",
    }
    values.update({k: str(v) for k, v in overrides.items()})
    return values


def _gate_vars(db: str, base_r5_inventory: str, **overrides) -> dict[str, str]:
    values = {
        "base_r5_inventory": base_r5_inventory,
        "recon_timeout_ms": RECON_TIMEOUT_MS,
        "lock_timeout_ms": LOCK_TIMEOUT_MS,
        "worker_role": WORKER_ROLE,
        "readonly_role": READONLY_ROLE,
    }
    values.update(overrides)
    return _vars(db, **values)


def _notification_gate_vars(db: str, base_r5_notification: str, **overrides) -> dict[str, str]:
    values = {
        "base_r5_notification": base_r5_notification,
        "recon_timeout_ms": RECON_TIMEOUT_MS,
    }
    values.update(overrides)
    return _vars(db, **values)


def _verify_vars(
    db: str, baseline_excl_cutover: str, base_r5_inventory: str, **overrides
) -> dict[str, str]:
    values = {
        "baseline_excl_cutover": baseline_excl_cutover,
        "base_r5_inventory": base_r5_inventory,
        "verify_timeout_ms": VERIFY_TIMEOUT_MS,
    }
    values.update(overrides)
    return _vars(db, **values)


def _notification_verify_vars(db: str, base_r5_notification: str, **overrides) -> dict[str, str]:
    values = {
        "base_r5_notification": base_r5_notification,
        "verify_timeout_ms": VERIFY_TIMEOUT_MS,
    }
    values.update(overrides)
    return _vars(db, **values)


def _break_glass_vars(db: str, **overrides) -> dict[str, str]:
    values = {
        "break_glass_attestation": "owner-authorized-break-glass",
        "break_glass_timeout_ms": BREAK_GLASS_TIMEOUT_MS,
    }
    values.update(overrides)
    return _vars(db, **values)


@contextlib.contextmanager
def _exclusive_lock_on_inventory_event(engine):
    """Hold ACCESS EXCLUSIVE so a psql gate read blocks and hits lock_timeout."""
    from sqlalchemy import text

    conn = engine.connect()
    trans = conn.begin()
    try:
        conn.execute(text("LOCK TABLE inventory_event IN ACCESS EXCLUSIVE MODE"))
        yield
    finally:
        trans.rollback()
        conn.close()


def _inject_r1_variance(engine) -> None:
    """HARNESS-ONLY negative fixture. Not part of the operator command set.

    Appends one truth event for a sku that has no snapshot row, which makes R1's
    variance non-zero. It is an INSERT and nothing else: even the negative
    fixture respects the append-only evidence rule, and it runs only against the
    throwaway database named by DB_NEG.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO inventory_event "
                "(shop_id, sku, event_type, quantity_delta, idempotency_key, created_at) "
                "VALUES (:shop, 'HARNESS-VARIANCE', 'loss', -3, "
                "'harness:r1-variance:1', NOW())"
            ),
            {"shop": PINNED_SHOP_ID},
        )


def _inject_overlay_reverse_violation(engine) -> None:
    """HARNESS-ONLY negative fixture for R1c arm (c). Not an operator command.

    Frozen DESIGN.md puts ``reverse`` inside OVERLAY when the reversed event is
    itself OVERLAY, and requires ``quantity_delta = 0`` for every overlay event.
    ``ck_overlay_zero_delta`` in ``models_truth.py`` enforces that only for the
    five listed types, so a ``reverse`` of a ``reserve`` carrying a non-zero
    delta is accepted by the schema while violating the contract. R1 sums every
    delta with no event_type filter, so without R1c arm (c) that row would flow
    into ``event_remaining`` unnoticed.

    Two INSERTs and nothing else, against DB_NEG only. The reserve row is legal
    and is left in place: it is the evidence arm (c) resolves against.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        reserve_id = conn.execute(
            text(
                "INSERT INTO inventory_event "
                "(shop_id, sku, event_type, quantity_delta, idempotency_key, created_at) "
                "VALUES (:shop, 'HARNESS-OVERLAY', 'reserve', 0, "
                "'harness:r1c-reserve:1', NOW()) RETURNING id"
            ),
            {"shop": PINNED_SHOP_ID},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO inventory_event "
                "(shop_id, sku, event_type, quantity_delta, reverses_event_id, "
                " idempotency_key, created_at) "
                "VALUES (:shop, 'HARNESS-OVERLAY', 'reverse', 5, :reversed, "
                "'harness:r1c-reverse:1', NOW())"
            ),
            {"shop": PINNED_SHOP_ID, "reversed": reserve_id},
        )


def _decode(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


def _api_client(pg: Pg16, monkeypatch, db: str):
    """The real admin and health routers over the runtime role, in staging mode."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError, ProgrammingError
    from sqlalchemy.orm import sessionmaker

    from app.config import settings
    from app.database import get_db
    from app.errors import FeatureNotReadyError
    from app.main import (
        feature_not_ready_handler,
        operational_error_handler,
        programming_error_handler,
    )
    from app.routers import admin as admin_router
    from app.routers import health as health_router

    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr("app.auth.identity.decode_bearer_user_id", _decode)
    monkeypatch.setattr("app.auth.clerk.decode_bearer_user_id", _decode)

    session_factory = sessionmaker(
        bind=pg.engine(db, READ_ROLE), autocommit=False, autoflush=False
    )
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api/v1")
    app.include_router(health_router.router, prefix="/api/v1")
    app.add_exception_handler(FeatureNotReadyError, feature_not_ready_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(ProgrammingError, programming_error_handler)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False)


def _probe_payload(**overrides) -> dict:
    body = {
        "sku": "HARNESS-PROBE-0001",
        "name": "Harness probe card - must never be received",
        "quantity": 1,
        "unit_cost": 0.01,
        "set_name": "Harness Set",
        "sequence_number": "1",
    }
    body.update(overrides)
    return body


class ProbeLog:
    """Every receive probe must fail closed. One 2xx fails the whole harness."""

    def __init__(self):
        self.entries: list[tuple[str, int]] = []

    def record(self, label: str, response) -> int:
        self.entries.append((label, response.status_code))
        assert response.status_code >= 300, (
            f"a receive probe succeeded, which this packet forbids: "
            f"{label} -> {response.status_code} {response.text}"
        )
        return response.status_code

    def assert_no_success(self) -> None:
        assert all(code >= 300 for _, code in self.entries), self.entries


def _envelope_counts(pg: Pg16, db: str) -> dict[str, int]:
    counts = {}
    for table in ("purchase_record", "acquisition_lot", "inventory_event", "inventory_item"):
        counts[table] = int(
            pg.scalar(
                db,
                f"SELECT count(*) FROM {table} WHERE shop_id = :shop",
                {"shop": PINNED_SHOP_ID},
            )
        )
    return counts


def _reserved_key_rows(pg: Pg16, db: str) -> int:
    return int(
        pg.scalar(
            db,
            "SELECT count(*) FROM purchase_record WHERE client_idempotency_key = :key",
            {"key": RESERVED_KEY},
        )
    )


@pytest.fixture()
def pg():
    """One fresh disposable postgres:16 container per test, destroyed at teardown."""
    from sqlalchemy import create_engine, text

    port = _free_port()
    container = f"stashtab-f2cut-{uuid_mod.uuid4().hex[:8]}"
    try:
        _run(
            [
                "docker", "run", "-d", "--name", container,
                "-e", f"POSTGRES_PASSWORD={SUPERUSER_PASSWORD}",
                "-p", f"{port}:5432",
                IMAGE,
            ]
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        pytest.skip(f"docker container could not start: {exc}")

    harness = Pg16(container, port)
    try:
        bootstrap = create_engine(_admin_url(port), pool_pre_ping=True)
        for _ in range(60):
            try:
                with bootstrap.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.skip("postgres:16 did not become ready")
        bootstrap.dispose()

        with harness.engine("postgres").connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            for role, secret in ROLE_PASSWORDS.items():
                conn.execute(
                    text(
                        f"CREATE ROLE {role} LOGIN PASSWORD '{secret}' "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
                    )
                )
        _run(["docker", "cp", str(SQL_DIR), f"{container}:{CONTAINER_SQL_DIR}"])
        yield harness
    finally:
        harness.dispose()
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)


ZERO_ENVELOPE = {
    "purchase_record": 0,
    "acquisition_lot": 0,
    "inventory_event": 0,
    "inventory_item": 0,
}


@pytest.mark.parametrize("fresh_db", ["first-fresh-db", "second-fresh-db"])
class TestF2CutoverPacket:
    """The whole packet is proved twice, each time from a fresh container.

    H4 determinism, H8 no evidence deleted, and H9 rerun behavior live here.
    """

    def test_packet_sequence_is_deterministic_and_rerun_safe(self, pg, fresh_db):
        db = DB_MAIN
        pg.provision(db)

        before = pg.catalog_counts(db)
        assert before["inventory_truth_cutover"] == 0

        step1 = pg.psql(db, WRITE_ROLE, "01-preflight.sql", _vars(db))
        assert step1.ok, step1

        step2 = pg.psql(db, WRITE_ROLE, "02-baseline.sql", _vars(db))
        assert step2.ok, step2
        baseline_all = _first_value(step2.stdout, "baseline_digest")
        baseline_excl = _first_value(step2.stdout, "baseline_excl_cutover")
        base_r5_inv = _first_value(step2.stdout, "r5_inventory_digest")
        # F6 compares against the digest that excludes the cutover relation.
        # If the two were equal, step 3's write would be invisible to F6.
        assert re.fullmatch(r"[0-9a-f]{32}", baseline_excl)
        assert baseline_all != baseline_excl

        step2b = pg.psql(db, WRITE_ROLE, "02b-baseline-notification.sql", _vars(db))
        assert step2b.ok, step2b
        base_r5_notif = _first_value(step2b.stdout, "r5_notification_digest")
        assert re.fullmatch(r"[0-9a-f]{32}", base_r5_notif)

        step3 = pg.psql(db, WRITE_ROLE, "03-write-locking.sql", _vars(db))
        assert step3.ok, step3
        assert _first_value(step3.stdout, "w0_cutover_table_empty") == "zero-rows-before-write"
        assert _first_value(step3.stdout, "w2_row_discipline") == "exactly-one-row-pinned-shop-gen1"
        assert _first_value(step3.stdout, "w3_row_shape") == "locking-with-frozen_at"

        step4 = pg.psql(db, WRITE_ROLE, "04-verify-locking.sql", _vars(db))
        assert step4.ok, step4
        assert _first_value(step4.stdout, "v4_gate_visible_status") == "gate-reads-locking"

        # H9: step 1 has no resume path. Once the row exists, preflight stops.
        step1_again = pg.psql(db, WRITE_ROLE, "01-preflight.sql", _vars(db))
        assert step1_again.failed_with("f2_preflight_p7_cutover_row_already_exists"), step1_again

        # H9: step 4 is the idempotent validation path and may be rerun freely.
        step4_again = pg.psql(db, WRITE_ROLE, "04-verify-locking.sql", _vars(db))
        assert step4_again.ok, step4_again
        assert step4_again.stdout == step4.stdout

        # H4: the gate is deterministic. Two runs over unchanged state must
        # agree on every assertion column, not merely both exit zero.
        gate_vars = _gate_vars(db, base_r5_inv)
        gate_a = pg.psql(db, WRITE_ROLE, "05-r1-r7.sql", gate_vars)
        assert gate_a.ok, gate_a
        gate_b = pg.psql(db, WRITE_ROLE, "05-r1-r7.sql", gate_vars)
        assert gate_b.ok, gate_b
        for token in GATE_TOKENS:
            assert token in gate_a.stdout, token
        assert [_first_value(gate_a.stdout, column) for column in GATE_COLUMNS] == [
            _first_value(gate_b.stdout, column) for column in GATE_COLUMNS
        ]
        assert _first_value(gate_a.stdout, "gate_evaluation_point") == "evaluating-at-locking"
        # R1e/R2c honest context: at step 5 the packet has written nothing but
        # the cutover row, so R1 and R2 examine zero rows and their zeros are
        # trivial. Asserting the counts keeps the audit entry honest instead of
        # letting an empty-set zero be read as a reconciliation of live stock.
        assert _first_value(gate_a.stdout, "r1_snapshot_rows_examined") == "0"
        assert _first_value(gate_a.stdout, "r1_event_rows_examined") == "0"
        assert _first_value(gate_a.stdout, "r2_rows_examined") == "0"

        notif_vars = _notification_gate_vars(db, base_r5_notif)
        gate_n_a = pg.psql(db, WRITE_ROLE, "05b-r5-notification.sql", notif_vars)
        assert gate_n_a.ok, gate_n_a
        gate_n_b = pg.psql(db, WRITE_ROLE, "05b-r5-notification.sql", notif_vars)
        assert gate_n_b.ok, gate_n_b
        assert gate_n_a.stdout == gate_n_b.stdout
        assert _first_value(gate_n_a.stdout, "r5b_result") == "R5b-unchanged"
        assert (
            _first_value(gate_n_a.stdout, "r5b_pinned_shop_rows")
            == "R5b-zero-rows-for-pinned-shop"
        )

        step6 = pg.psql(
            db, WRITE_ROLE, "06-write-complete.sql",
            _vars(db, gate_attestation="r1-r7-zero-variance"),
        )
        assert step6.ok, step6
        assert _first_value(step6.stdout, "t1_rows_transitioned") == "one-row-transitioned"
        assert (
            _first_value(step6.stdout, "t2_row_shape")
            == "complete-with-opened_at-after-frozen_at"
        )
        assert _first_value(step6.stdout, "t3_row_discipline") == "pinned-shop-gen1-only"
        assert _first_value(step6.stdout, "t4_no_envelope_writes") == "no-envelope-rows-written"

        # H9: step 6 is not idempotent by design. A second run finds the row in
        # 'complete' and stops rather than rewriting opened_at.
        step6_again = pg.psql(
            db, WRITE_ROLE, "06-write-complete.sql",
            _vars(db, gate_attestation="r1-r7-zero-variance"),
        )
        assert step6_again.failed_with(
            "f2_complete_t0b_row_is_not_in_the_locking_state"
        ), step6_again

        verify_vars = _verify_vars(db, baseline_excl, base_r5_inv)
        step7 = pg.psql(db, WRITE_ROLE, "07-final-verification.sql", verify_vars)
        assert step7.ok, step7
        assert _first_value(step7.stdout, "f1_r4_result") == "R4-zero-at-complete"
        assert _first_value(step7.stdout, "f2_gate_visible_status") == "gate-reads-complete"
        assert _first_value(step7.stdout, "f3_open_gate_tenants") == "one-tenant-open"
        assert _first_value(step7.stdout, "f4_r1_result") == "R1-zero"
        assert _first_value(step7.stdout, "f6b_r5a_stability") == "R5a-unchanged-at-step-7"
        assert _first_value(step7.stdout, "f8_no_receive_performed") == "no-receive-performed"
        step7_again = pg.psql(db, WRITE_ROLE, "07-final-verification.sql", verify_vars)
        assert step7_again.ok, step7_again

        step7b = pg.psql(
            db, WRITE_ROLE, "07b-verify-notification.sql",
            _notification_verify_vars(db, base_r5_notif),
        )
        assert step7b.ok, step7b
        assert _first_value(step7b.stdout, "nb1v_evaluation_point") == "verifying-at-complete"
        assert _first_value(step7b.stdout, "f10_r5b_stability") == "R5b-unchanged-at-step-7"
        assert (
            _first_value(step7b.stdout, "f11_pinned_shop_rows")
            == "R5b-zero-rows-for-pinned-shop"
        )

        # H8 forward path: the only relation that moved is the cutover row.
        after = pg.catalog_counts(db)
        assert set(after) == set(before), sorted(set(after) ^ set(before))
        moved = {rel: (before[rel], after[rel]) for rel in before if before[rel] != after[rel]}
        assert moved == {"inventory_truth_cutover": (0, 1)}, moved

        assert _envelope_counts(pg, db) == ZERO_ENVELOPE
        assert _reserved_key_rows(pg, db) == 0

    def test_wrong_database_role_and_shop_fail_closed(self, pg, fresh_db):
        """H1 and H2: every wrong-target path stops before anything is written."""
        db = DB_MAIN
        pg.provision(db)
        pg.create_database(DB_WRONG)  # deliberately empty: no schema at all

        # H1a wrong database. G3 fires before any relation is touched.
        wrong_db = pg.psql(DB_WRONG, WRITE_ROLE, "01-preflight.sql", _vars(db))
        assert wrong_db.failed_with("f2_guard_unexpected_database"), wrong_db

        # H1b wrong role, caught by the session guard.
        wrong_role = pg.psql(db, READ_ROLE, "03-write-locking.sql", _vars(db))
        assert wrong_role.failed_with(
            "f2_guard_session_is_not_the_expected_role"
        ), wrong_role

        # H1b again with the guard satisfied, so the database itself has to be
        # the thing that refuses: the runtime role cannot INSERT the row.
        wrong_role_honest = pg.psql(
            db, READ_ROLE, "03-write-locking.sql", _vars(db, expected_role=READ_ROLE)
        )
        assert wrong_role_honest.failed_with(
            "f2_write_locking_w0b_session_cannot_insert_cutover_row"
        ), wrong_role_honest

        # H1c malformed tenant.
        malformed = pg.psql(
            db, WRITE_ROLE, "01-preflight.sql", _vars(db, cutover_shop_id="smoke-shop-b")
        )
        assert malformed.failed_with(
            "f2_guard_missing_or_invalid_cutover_shop_id"
        ), malformed

        # H1c double-entry disagreement: a well-formed but different tenant.
        disagree = pg.psql(
            db, WRITE_ROLE, "01-preflight.sql", _vars(db, cutover_shop_id=CONTROL_SHOP_ID)
        )
        assert disagree.failed_with(
            "f2_guard_cutover_shop_id_does_not_match_the_pinned_shop_id"
        ), disagree

        # H1c a well-formed UUID that is not a tenant of this database.
        absent = pg.psql(
            db, WRITE_ROLE, "01-preflight.sql",
            _vars(db, cutover_shop_id=ABSENT_SHOP_ID, pinned_shop_id=ABSENT_SHOP_ID),
        )
        assert absent.failed_with("f2_guard_pinned_shop_absent_or_ambiguous"), absent

        # H2 no second generation, and no duplicate generation.
        second_generation = pg.psql(
            db, WRITE_ROLE, "03-write-locking.sql", _vars(db, cutover_generation="2")
        )
        assert second_generation.failed_with(
            "f2_guard_generation_must_be_exactly_one"
        ), second_generation

        assert pg.psql(db, WRITE_ROLE, "03-write-locking.sql", _vars(db)).ok

        # H9: a rerun of step 3 is refused by the packet's own precondition W0,
        # which requires a globally empty cutover relation. That guard fires
        # before the INSERT, so nothing is written and the unique constraint is
        # never reached.
        duplicate = pg.psql(db, WRITE_ROLE, "03-write-locking.sql", _vars(db))
        assert duplicate.failed_with(
            "f2_write_locking_w0_a_cutover_row_already_exists"
        ), duplicate

        # H2 backstop: the accepted schema refuses a duplicate generation on its
        # own, independently of the packet guard, so even a hand-written INSERT
        # cannot create a second generation-1 row. The probe is expected to be
        # rejected and therefore writes nothing.
        raw_duplicate = pg.psql(
            db,
            WRITE_ROLE,
            sql=(
                "INSERT INTO inventory_truth_cutover "
                "(shop_id, generation, status, frozen_at, created_at) VALUES "
                f"('{PINNED_SHOP_ID}', 1, 'locking', now(), now())"
            ),
        )
        assert not raw_duplicate.ok, raw_duplicate
        assert "uq_cutover_shop_generation" in raw_duplicate.stderr, raw_duplicate

        rows = [tuple(row) for row in pg.query(
            db, "SELECT shop_id, generation, status FROM inventory_truth_cutover"
        )]
        assert rows == [(PINNED_SHOP_ID, 1, "locking")], rows
        assert _envelope_counts(pg, db) == ZERO_ENVELOPE

    def test_timeout_error_and_mismatch_cannot_pass(self, pg, fresh_db):
        """H5: a timeout, a variance, a missing parameter and a wrong attestation
        each produce a non-zero exit and never a green gate."""
        db = DB_NEG
        pg.provision(db)

        assert pg.psql(db, WRITE_ROLE, "01-preflight.sql", _vars(db)).ok
        step2 = pg.psql(db, WRITE_ROLE, "02-baseline.sql", _vars(db))
        assert step2.ok, step2
        base_r5_inv = _first_value(step2.stdout, "r5_inventory_digest")
        assert pg.psql(db, WRITE_ROLE, "03-write-locking.sql", _vars(db)).ok
        # The negative database starts from exactly the same pre-receive state
        # as the positive one, before the harness injects anything.
        assert _envelope_counts(pg, db) == ZERO_ENVELOPE

        # A missing required variable is a syntax error, never a silent default.
        incomplete = {k: v for k, v in _vars(db).items() if k != "cutover_shop_id"}
        missing_var = pg.psql(db, WRITE_ROLE, "01-preflight.sql", incomplete)
        assert not missing_var.ok, missing_var
        assert "syntax error" in missing_var.stderr, missing_var

        missing_gate_var = pg.psql(db, WRITE_ROLE, "06-write-complete.sql", _vars(db))
        assert not missing_gate_var.ok, missing_gate_var
        assert "syntax error" in missing_gate_var.stderr, missing_gate_var

        # An out-of-range timeout is refused before the gate opens.
        bad_timeout = pg.psql(
            db, WRITE_ROLE, "05-r1-r7.sql",
            _gate_vars(db, base_r5_inv, recon_timeout_ms="1"),
        )
        assert bad_timeout.failed_with("f2_gate_timeout_parameters_out_of_range"), bad_timeout

        # A genuine server-side lock timeout cannot be mistaken for a pass.
        with _exclusive_lock_on_inventory_event(pg.engine(db, SUPERUSER)):
            blocked = pg.psql(
                db, WRITE_ROLE, "05-r1-r7.sql",
                _gate_vars(db, base_r5_inv, lock_timeout_ms="100"),
            )
        assert not blocked.ok, blocked
        assert "lock timeout" in blocked.stderr, blocked
        assert "R1-zero" not in blocked.stdout

        # A real R1 variance cannot be mistaken for a pass. Injected first,
        # while the overlay state is still clean, so the failure is attributable
        # to the R1b verdict rather than to a precondition.
        _inject_r1_variance(pg.engine(db, WRITE_ROLE))
        mismatch = pg.psql(db, WRITE_ROLE, "05-r1-r7.sql", _gate_vars(db, base_r5_inv))
        assert mismatch.failed_with("f2_gate_r1_snapshot_and_truth_variance"), mismatch
        assert "R1-zero" not in mismatch.stdout

        # R1c arm (c): a 'reverse' of an overlay event carrying a non-zero delta
        # is accepted by ck_overlay_zero_delta but forbidden by frozen DESIGN.md.
        # Injected second, so this run proves the precondition fires ahead of the
        # R1b verdict: once an overlay violation exists, R1c stops the file and
        # the R1b marker can never be printed again in this database.
        _inject_overlay_reverse_violation(pg.engine(db, WRITE_ROLE))
        overlay = pg.psql(db, WRITE_ROLE, "05-r1-r7.sql", _gate_vars(db, base_r5_inv))
        assert overlay.failed_with(
            "f2_gate_r1c_overlay_event_has_a_non_zero_delta"
        ), overlay
        assert "R1-zero" not in overlay.stdout
        assert "overlay-deltas-are-zero" not in overlay.stdout

        # Step 6 refuses a wrong attestation and leaves the row in 'locking'.
        wrong_attestation = pg.psql(
            db, WRITE_ROLE, "06-write-complete.sql",
            _vars(db, gate_attestation="looks-fine-to-me"),
        )
        assert wrong_attestation.failed_with(
            "f2_complete_t0_gate_attestation_missing_or_wrong"
        ), wrong_attestation

        statuses = [row[0] for row in pg.query(db, "SELECT status FROM inventory_truth_cutover")]
        assert statuses == ["locking"], statuses
        # The three injected truth events are the only envelope rows this test
        # ever creates: the legal 'reserve', the contract-violating 'reverse' of
        # it, and the R1 variance event. purchase_record, acquisition_lot and
        # inventory_item stay at zero, so even the negative database shows that
        # no receive happened.
        assert _envelope_counts(pg, db) == {
            "purchase_record": 0,
            "acquisition_lot": 0,
            "inventory_event": 3,
            "inventory_item": 0,
        }
        assert _reserved_key_rows(pg, db) == 0

    def test_locking_blocks_receive_and_break_glass_restores_it(self, pg, monkeypatch, fresh_db):
        """H3, H6 and H7 over the real routers, plus the reserved-key finding."""
        db = DB_MAIN
        pg.provision(db)
        probes = ProbeLog()

        assert pg.psql(db, WRITE_ROLE, "01-preflight.sql", _vars(db)).ok
        step2 = pg.psql(db, WRITE_ROLE, "02-baseline.sql", _vars(db))
        assert step2.ok, step2
        step2b = pg.psql(db, WRITE_ROLE, "02b-baseline-notification.sql", _vars(db))
        assert step2b.ok, step2b
        baseline_excl = _first_value(step2.stdout, "baseline_excl_cutover")
        base_r5_inv = _first_value(step2.stdout, "r5_inventory_digest")
        base_r5_notif = _first_value(step2b.stdout, "r5_notification_digest")

        assert pg.psql(db, WRITE_ROLE, "03-write-locking.sql", _vars(db)).ok
        client = _api_client(pg, monkeypatch, db)

        # H3(i) unauthenticated receive is 401, before shop and gate lookups.
        anonymous = client.post(
            RECEIVE_URL,
            json=_probe_payload(),
            headers={"X-Shop-Id": PINNED_SHOP_ID, "Idempotency-Key": str(uuid_mod.uuid4())},
        )
        assert probes.record("unauthenticated", anonymous) == 401

        # H3(ii) authenticated receive while locking is a controlled 503.
        gated = client.post(
            RECEIVE_URL,
            json=_probe_payload(),
            headers={
                "X-Shop-Id": PINNED_SHOP_ID,
                "Authorization": f"Bearer {PINNED_OWNER}",
                "Idempotency-Key": str(uuid_mod.uuid4()),
            },
        )
        assert probes.record("authenticated-while-locking", gated) == 503
        assert gated.json()["error"] == "FEATURE_NOT_READY"

        # The reserved key is not a UUIDv4, so _validated_client_key rejects it
        # before the readiness gate is reached. Recorded as a finding for the
        # later receive unlock; this packet does not touch application code.
        reserved = client.post(
            RECEIVE_URL,
            json=_probe_payload(),
            headers={
                "X-Shop-Id": PINNED_SHOP_ID,
                "Authorization": f"Bearer {PINNED_OWNER}",
                "Idempotency-Key": RESERVED_KEY,
            },
        )
        assert probes.record("reserved-key-not-uuidv4", reserved) == 422

        absent_key = client.post(
            RECEIVE_URL,
            json=_probe_payload(),
            headers={"X-Shop-Id": PINNED_SHOP_ID, "Authorization": f"Bearer {PINNED_OWNER}"},
        )
        assert probes.record("missing-idempotency-key", absent_key) == 422

        assert _envelope_counts(pg, db) == ZERO_ENVELOPE
        assert _reserved_key_rows(pg, db) == 0

        gate = pg.psql(db, WRITE_ROLE, "05-r1-r7.sql", _gate_vars(db, base_r5_inv))
        assert gate.ok, gate
        gate_notification = pg.psql(
            db, WRITE_ROLE, "05b-r5-notification.sql",
            _notification_gate_vars(db, base_r5_notif),
        )
        assert gate_notification.ok, gate_notification

        step6 = pg.psql(
            db, WRITE_ROLE, "06-write-complete.sql",
            _vars(db, gate_attestation="r1-r7-zero-variance"),
        )
        assert step6.ok, step6

        # H6: exactly one row exists, it belongs to Smoke Shop B, and the
        # control tenant has no row at all, so its gate stays closed.
        rows = [tuple(row) for row in pg.query(
            db,
            "SELECT shop_id, generation, status, frozen_at IS NOT NULL, "
            "opened_at IS NOT NULL FROM inventory_truth_cutover ORDER BY id",
        )]
        assert rows == [(PINNED_SHOP_ID, 1, "complete", True, True)], rows

        control_tenant = client.post(
            RECEIVE_URL,
            json=_probe_payload(),
            headers={
                "X-Shop-Id": CONTROL_SHOP_ID,
                "Authorization": f"Bearer {CONTROL_OWNER}",
                "Idempotency-Key": str(uuid_mod.uuid4()),
            },
        )
        assert probes.record("control-shop-after-complete", control_tenant) == 503

        # The global readiness flag does not become true. features.inventory_cutover
        # is a hard-coded False in app/readiness.py and this packet does not
        # change it, so a green cutover never implies a green readiness payload.
        ready = client.get(READY_URL)
        assert ready.json()["features"]["inventory_cutover"] is False

        # No probe is sent for the pinned shop while its gate is open. Step 8 of
        # the runbook stops without receiving, and so does this harness.
        step7 = pg.psql(
            db, WRITE_ROLE, "07-final-verification.sql",
            _verify_vars(db, baseline_excl, base_r5_inv),
        )
        assert step7.ok, step7
        assert _first_value(step7.stdout, "f3_open_gate_tenants") == "one-tenant-open"
        assert _first_value(step7.stdout, "f8_no_receive_performed") == "no-receive-performed"
        step7b = pg.psql(
            db, WRITE_ROLE, "07b-verify-notification.sql",
            _notification_verify_vars(db, base_r5_notif),
        )
        assert step7b.ok, step7b

        # H7 and H8: break-glass withdraws exactly the pinned row, preserves
        # every piece of audit evidence, and deletes nothing anywhere.
        pre_image = tuple(pg.query(
            db, "SELECT id, created_at, frozen_at, opened_at FROM inventory_truth_cutover"
        )[0])
        counts_before = pg.catalog_counts(db)

        break_glass = pg.psql(db, WRITE_ROLE, "08-break-glass-locking.sql", _break_glass_vars(db))
        assert break_glass.ok, break_glass
        assert _first_value(break_glass.stdout, "bg2_rows_withdrawn") == "one-row-withdrawn"
        assert (
            _first_value(break_glass.stdout, "bg1b_counting_self_test")
            == f"{len(counts_before)}-relations-counted"
        )
        assert (
            _first_value(break_glass.stdout, "bg3_evidence_preserved")
            == "evidence-preserved-status-only-changed"
        )
        assert (
            _first_value(break_glass.stdout, "bg4_no_rows_deleted")
            == "all-row-counts-unchanged"
        )
        assert _first_value(break_glass.stdout, "bg6_gate_fail_closed") == "gate-reads-locking"
        assert pg.catalog_counts(db) == counts_before

        post_image = [tuple(row) for row in pg.query(
            db,
            "SELECT id, shop_id, generation, status, created_at, frozen_at, opened_at "
            "FROM inventory_truth_cutover",
        )]
        assert len(post_image) == 1, post_image
        row = post_image[0]
        assert row[0] == pre_image[0], "id must not change"
        assert (row[1], row[2]) == (PINNED_SHOP_ID, 1)
        assert row[3] == "locking"
        assert row[4] == pre_image[1], "created_at is evidence and must not change"
        assert row[5] == pre_image[2], "frozen_at is evidence and must not change"
        assert row[6] == pre_image[3], "opened_at is evidence and must not be nulled"
        assert row[6] is not None

        # H9: break-glass is not repeatable. A second run finds no 'complete'
        # row and stops instead of rewriting the row that is already locking.
        break_glass_again = pg.psql(
            db, WRITE_ROLE, "08-break-glass-locking.sql", _break_glass_vars(db)
        )
        assert break_glass_again.failed_with(
            "f2_break_glass_bg0c_no_complete_row_to_withdraw"
        ), break_glass_again

        # H3 restored: the pinned tenant is fail-closed again after withdrawal.
        regated = client.post(
            RECEIVE_URL,
            json=_probe_payload(),
            headers={
                "X-Shop-Id": PINNED_SHOP_ID,
                "Authorization": f"Bearer {PINNED_OWNER}",
                "Idempotency-Key": str(uuid_mod.uuid4()),
            },
        )
        assert probes.record("after-break-glass", regated) == 503

        assert _envelope_counts(pg, db) == ZERO_ENVELOPE
        assert _reserved_key_rows(pg, db) == 0
        probes.assert_no_success()
