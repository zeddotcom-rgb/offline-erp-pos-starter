"""Database adapter for local SQLite or shared PostgreSQL deployments.

Set DB_BACKEND=sqlite for the offline single-PC mode (default).
Set DB_BACKEND=postgresql and DATABASE_URL for LAN/server mode.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from config import DB_PATH

_ID_TABLES = {"company", "user_account", "customer", "supplier", "item", "item_price",
              "stock_move", "invoice", "invoice_item", "license", "audit_log"}


class _BufferedCursor:
    def __init__(self, cursor, lastrowid=None, buffered=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self._buffered = buffered

    def fetchone(self):
        if self._buffered is not None:
            row, self._buffered = self._buffered, None
            return row
        return self._cursor.fetchone()

    def fetchall(self):
        rows = []
        if self._buffered is not None:
            rows.append(self._buffered)
            self._buffered = None
        rows.extend(self._cursor.fetchall())
        return rows

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _PostgresConnection:
    def __init__(self, raw):
        self._raw = raw

    @staticmethod
    def _sql(sql: str) -> str:
        sql = sql.strip()
        if sql.upper() == "BEGIN IMMEDIATE":
            sql = "BEGIN"
        # Application SQL uses DB-API qmark parameters; psycopg uses %s.
        sql = sql.replace("?", "%s")
        match = re.match(r"(?is)^INSERT\s+INTO\s+([a-z_][a-z0-9_]*)", sql)
        if match and match.group(1).lower() in _ID_TABLES and not re.search(r"\bRETURNING\b", sql, re.I):
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        return sql

    def execute(self, sql: str, params: Any = ()):
        # Translate SQLite's schema introspection to PostgreSQL information_schema.
        m = re.match(r"(?is)^PRAGMA\s+table_info\((\w+)\)\s*;?$", sql.strip())
        if m:
            cursor = self._raw.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position",
                (m.group(1).lower(),),
            )
            return _BufferedCursor(cursor)
        if "sqlite_master" in sql.lower():
            raise RuntimeError("Use database.table_exists(); sqlite_master is SQLite-specific.")
        translated = self._sql(sql)
        cursor = self._raw.execute(translated, params or ())
        if re.search(r"(?is)^INSERT\s+INTO\s+([a-z_][a-z0-9_]*)", translated):
            table = re.match(r"(?is)^INSERT\s+INTO\s+([a-z_][a-z0-9_]*)", translated).group(1).lower()
            if table in _ID_TABLES and re.search(r"\bRETURNING\s+id\s*$", translated, re.I):
                row = cursor.fetchone()
                return _BufferedCursor(cursor, lastrowid=(row["id"] if row else None), buffered=row)
        return _BufferedCursor(cursor)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _backend() -> str:
    value = os.environ.get("DB_BACKEND", "postgresql" if os.environ.get("DATABASE_URL", "").startswith(("postgres://", "postgresql://")) else "sqlite")
    value = value.lower().strip()
    if value not in {"sqlite", "postgresql", "postgres"}:
        raise ValueError("DB_BACKEND must be sqlite or postgresql.")
    return "postgresql" if value == "postgres" else value


def get_connection():
    if _backend() == "sqlite":
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required when DB_BACKEND=postgresql.")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("Install the PostgreSQL driver with: pip install 'psycopg[binary]'") from exc
    options = {}
    schema = os.environ.get("PGSCHEMA")
    if schema:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
            raise ValueError("PGSCHEMA must be a simple PostgreSQL schema identifier.")
        options["options"] = f"-c search_path={schema}"
    raw = psycopg.connect(url, row_factory=dict_row, **options)
    return _PostgresConnection(raw)


def get_columns(conn, table: str) -> set[str]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError("Invalid table name.")
    if _backend() == "sqlite":
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return {row["name"] for row in conn.execute(
        "SELECT column_name AS name FROM information_schema.columns "
        "WHERE table_schema=current_schema() AND table_name=?", (table.lower(),)
    ).fetchall()}


def table_exists(conn, table: str) -> bool:
    if _backend() == "sqlite":
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?",
        (table.lower(),),
    ).fetchone())


def init_db():
    schema_name = "schema_postgres.sql" if _backend() == "postgresql" else "schema.sql"
    # PyInstaller --onefile extracts bundled data into sys._MEIPASS.
    # Use that directory when frozen, and the source directory in development.
    resource_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    schema_path = resource_dir / schema_name
    schema = schema_path.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        if _backend() == "sqlite":
            conn.executescript(schema)
        else:
            for statement in schema.split(";"):
                statement = statement.strip()
                if statement and not statement.upper().startswith("PRAGMA"):
                    conn.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
