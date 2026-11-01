"""Versioned, cross-database schema migrations.

Legacy rows are kept with company_id=NULL until one-time setup explicitly adopts them.
"""
from database import get_connection, get_columns

SCOPED_TABLES = (
    "user_account", "customer", "supplier", "item", "item_price",
    "stock_move", "invoice", "invoice_item", "license", "audit_log",
)


def _ensure_columns(conn):
    for table in SCOPED_TABLES:
        if "company_id" not in get_columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN company_id INTEGER")
    if "actor_id" not in get_columns(conn, "audit_log"):
        conn.execute("ALTER TABLE audit_log ADD COLUMN actor_id INTEGER")


def migrate() -> None:
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migration (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        versions = {int(row["version"]) for row in conn.execute("SELECT version FROM schema_migration").fetchall()}
        if 1 not in versions:
            _ensure_columns(conn)
            conn.execute("""CREATE TABLE IF NOT EXISTS setup_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                setup_completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT
            )""")
            conn.execute("INSERT INTO schema_migration(version) VALUES (1)")
        # Version 2 backfills the tenant column for license records on databases
        # that already applied the original v1 migration.
        if 2 not in versions:
            if "company_id" not in get_columns(conn, "license"):
                conn.execute("ALTER TABLE license ADD COLUMN company_id INTEGER")
            conn.execute("INSERT INTO schema_migration(version) VALUES (2)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
