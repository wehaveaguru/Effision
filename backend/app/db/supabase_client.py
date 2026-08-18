"""
DB client factory.

In production this returns a real `supabase-py` client pointed at Supabase.
When SUPABASE_URL / SUPABASE_KEY aren't set (e.g. this sandbox, CI, or a
laptop without a live Supabase project), it returns `LocalPostgresShim`
instead — a drop-in object that implements the same
`.table(...).select(...).eq(...).execute()` fluent surface, backed by a
local SQLite file.

This is what makes every phase of the pipeline testable end-to-end without
network access or credentials: `app/pipeline/*.py` never imports sqlite3 or
supabase directly, it only ever calls `get_client()`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv

_env_path = find_dotenv()
if not _env_path:
    for candidate in [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "app" / ".env",
    ]:
        if candidate.is_file():
            _env_path = str(candidate)
            break
load_dotenv(_env_path)


def _default_db_path() -> Path:
    # Read the env var lazily (not at import time) so tests can point this
    # at a fresh tmp_path per test via monkeypatch.
    return Path(os.environ.get("LOCAL_DB_PATH", "data/local_dev.db"))


# ---------------------------------------------------------------------------
# Result wrapper — mirrors supabase-py's APIResponse(.data / .count)
# ---------------------------------------------------------------------------
@dataclass
class ShimResponse:
    data: list[dict[str, Any]] = field(default_factory=list)
    count: int | None = None


class _QueryBuilder:
    """Chainable query builder mimicking supabase-py's PostgrestFilterBuilder,
    restricted to the subset of operations this codebase actually uses:
    select / insert / update / eq / order / limit / execute."""

    def __init__(self, conn: sqlite3.Connection, table: str):
        self._conn = conn
        self._table = table
        self._op: str | None = None
        self._select_cols = "*"
        self._payload: dict[str, Any] | None = None
        self._filters: list[tuple[str, Any]] = []
        self._order_by: str | None = None
        self._desc = False
        self._limit: int | None = None

    # -- verb setters --------------------------------------------------
    def select(self, cols: str = "*") -> "_QueryBuilder":
        self._op = "select"
        self._select_cols = cols
        return self

    def insert(self, payload: dict[str, Any] | list[dict[str, Any]]) -> "_QueryBuilder":
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> "_QueryBuilder":
        self._op = "update"
        self._payload = payload
        return self

    # -- filters ---------------------------------------------------------
    def eq(self, col: str, val: Any) -> "_QueryBuilder":
        self._filters.append((col, val))
        return self

    def order(self, col: str, desc: bool = False) -> "_QueryBuilder":
        self._order_by = col
        self._desc = desc
        return self

    def limit(self, n: int) -> "_QueryBuilder":
        self._limit = n
        return self

    # -- execution ---------------------------------------------------------
    def execute(self) -> ShimResponse:
        if self._op == "insert":
            return self._do_insert()
        if self._op == "update":
            return self._do_update()
        return self._do_select()

    # -- internals ---------------------------------------------------------
    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        out = {}
        for k in row.keys():
            v = row[k]
            if isinstance(v, str) and k in ("properties", "value") and v:
                try:
                    v = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    pass
            out[k] = v
        return out

    def _do_insert(self) -> ShimResponse:
        rows = self._payload if isinstance(self._payload, list) else [self._payload]
        out_rows = []
        cur = self._conn.cursor()
        for row in rows:
            row = dict(row)
            row.setdefault("id", str(uuid.uuid4()))
            for jcol in ("properties", "value"):
                if jcol in row and not isinstance(row[jcol], str):
                    row[jcol] = json.dumps(row[jcol])
            keys = list(row.keys())
            cols = ", ".join(keys)
            placeholders = ", ".join("?" for _ in keys)
            cur.execute(
                f"insert into {self._table} ({cols}) values ({placeholders})",
                [row[k] for k in keys],
            )
            out_rows.append(row)
        self._conn.commit()
        for r in out_rows:
            for jcol in ("properties", "value"):
                if jcol in r and isinstance(r[jcol], str):
                    try:
                        r[jcol] = json.loads(r[jcol])
                    except (json.JSONDecodeError, TypeError):
                        pass
        return ShimResponse(data=out_rows)

    def _do_update(self) -> ShimResponse:
        payload = dict(self._payload) if isinstance(self._payload, dict) else {}
        for jcol in ("properties", "value"):
            if jcol in payload and not isinstance(payload[jcol], str):
                payload[jcol] = json.dumps(payload[jcol])
        keys = list(payload.keys())
        set_clause = ", ".join(f"{k} = ?" for k in keys)
        vals = [payload[k] for k in keys]
        where_clause, where_vals = self._build_where()
        cur = self._conn.cursor()
        cur.execute(
            f"update {self._table} set {set_clause} {where_clause}", vals + where_vals
        )
        self._conn.commit()
        return self._do_select()

    def _do_select(self) -> ShimResponse:
        where_clause, where_vals = self._build_where()
        sql = f"select {self._select_cols} from {self._table} {where_clause}"
        if self._order_by:
            sql += f" order by {self._order_by} {'desc' if self._desc else 'asc'}"
        if self._limit:
            sql += f" limit {self._limit}"
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.cursor()
        cur.execute(sql, where_vals)
        rows = [self._row_to_dict(r) for r in cur.fetchall()]
        return ShimResponse(data=rows, count=len(rows))

    def _build_where(self) -> tuple[str, list[Any]]:
        if not self._filters:
            return "", []
        clause = " where " + " and ".join(f"{c} = ?" for c, _ in self._filters)
        return clause, [v for _, v in self._filters]


class _RpcBuilder:
    """Mimics supabase-py's PostgrestRPCFilterBuilder for the two RPCs
    defined in schema.sql, reimplemented against SQLite with a naive
    (non-vector) fallback: token-overlap similarity for `match_*`,
    LIKE-based scoring for `search_*_fts`."""

    def __init__(self, conn: sqlite3.Connection, fn_name: str, params: dict[str, Any]):
        self._conn = conn
        self._fn = fn_name
        self._params = params

    def execute(self) -> ShimResponse:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.cursor()
        cur.execute("select id, file_name, raw_text from source_documents")
        rows = [dict(r) for r in cur.fetchall()]

        query_text = self._params.get("query_text", "")
        match_count = self._params.get("match_count", 10)

        scored = []
        if self._fn in ("match_source_documents", "search_source_documents_fts"):
            terms = [t.lower() for t in query_text.split() if t]
            for r in rows:
                text = (r.get("raw_text") or "").lower()
                score = sum(text.count(t) for t in terms) if terms else 0
                scored.append({**r, "similarity": float(score), "rank": float(score)})
            scored.sort(key=lambda r: r["similarity"], reverse=True)

        return ShimResponse(data=scored[:match_count])


class LocalPostgresShim:
    """Drop-in stand-in for the supabase-py client, backed by SQLite.

    Swap for a real `supabase.create_client(url, key)` in production by
    setting SUPABASE_URL and SUPABASE_KEY — get_client() below picks
    whichever is available automatically.
    """

    def __init__(self, db_path: Path | None = None):
        db_path = db_path or _default_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("pragma foreign_keys = on")
        self._ensure_schema()

    def table(self, name: str) -> _QueryBuilder:
        return _QueryBuilder(self._conn, name)

    def rpc(self, fn_name: str, params: dict[str, Any]) -> _RpcBuilder:
        return _RpcBuilder(self._conn, fn_name, params)

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            create table if not exists nodes (
                id text primary key,
                node_type text not null,
                label text not null,
                properties text not null default '{}',
                created_at text default (datetime('now'))
            );

            create table if not exists source_documents (
                id text primary key,
                file_name text not null,
                file_type text not null,
                raw_text text,
                parsed_at text default (datetime('now'))
            );

            create table if not exists edges (
                id text primary key,
                source_node_id text not null references nodes(id),
                target_node_id text not null references nodes(id),
                relation text not null,
                value text,
                confidence real not null,
                source_document_id text not null references source_documents(id),
                status text not null default 'proposed',
                reviewed_by text,
                reviewed_at text,
                created_at text default (datetime('now'))
            );
            """
        )
        self._conn.commit()


_client_singleton = None


def get_client():
    """Returns a real Supabase client if credentials are configured,
    otherwise the local SQLite shim. This is the ONLY place in the codebase
    that should branch on which backend is active."""
    global _client_singleton
    if _client_singleton is not None:
        return _client_singleton

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        from supabase import create_client  # imported lazily — optional dep

        _client_singleton = create_client(url, key)
    else:
        _client_singleton = LocalPostgresShim()
    return _client_singleton