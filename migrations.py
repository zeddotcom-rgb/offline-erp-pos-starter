"""Versioned, cross-database schema migrations.

Existing business rows remain unassigned (company_id NULL) until the one-time setup
wizard explicitly adopts them. This avoids silently guessing tenant ownership.
"""
from database import get_connection, get_columns

SCOPED_TABLES = (
    "user_account", "customer", "supplier", "item", "item_price",
    "stock_move", "invoice", "invoice_item", "audit_log",
)


def migrate() -> None:
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migration (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        applied = conn.execute("SELECT 1 FROM schema_migration WHERE version=1").fetchone()
        if not applied:
            for table in SCOPED_TABLES:
                columns = get_columns(conn, table)
                if "company_id" not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN company_id INTEGER")
            audit_columns = get_columns(conn, "audit_log")
            if "actor_id" not in audit_columns:
                conn.execute("ALTER TABLE audit_log ADD COLUMN actor_id INTEGER")
            conn.execute("""CREATE TABLE IF NOT EXISTS setup_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                setup_completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT
            )""")
            conn.execute("INSERT INTO schema_migration(version) VALUES (1)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
