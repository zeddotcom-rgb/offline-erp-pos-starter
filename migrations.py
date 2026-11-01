"""Versioned, cross-database schema migrations.

Legacy rows remain unassigned until the one-time setup wizard explicitly adopts them.
"""
import sqlite3

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


def _scope_unique_constraints(conn, sqlite_backend):
    if sqlite_backend:
        # SQLite cannot drop a UNIQUE constraint in place. Rebuild only the two
        # affected tables with IDs and all existing business columns preserved.
        conn.execute("""CREATE TABLE item_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            barcode TEXT,
            hsn_sac TEXT,
            purchase_price REAL DEFAULT 0,
            sale_price REAL DEFAULT 0,
            mrp REAL DEFAULT 0,
            stock_qty REAL DEFAULT 0,
            min_stock REAL DEFAULT 0,
            max_stock REAL DEFAULT 0,
            gst_rate REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            company_id INTEGER
        )""")
        conn.execute("""INSERT INTO item_v4
            (id, code, name, category, barcode, hsn_sac, purchase_price, sale_price,
             mrp, stock_qty, min_stock, max_stock, gst_rate, is_active, created_at, company_id)
            SELECT id, code, name, category, barcode, hsn_sac, purchase_price, sale_price,
                   mrp, stock_qty, min_stock, max_stock, gst_rate, is_active, created_at, company_id
            FROM item""")
        conn.execute("DROP TABLE item")
        conn.execute("ALTER TABLE item_v4 RENAME TO item")

        conn.execute("""CREATE TABLE invoice_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL,
            customer_id INTEGER,
            total_amount REAL NOT NULL,
            discount_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            grand_total REAL NOT NULL,
            payment_mode TEXT,
            status TEXT DEFAULT 'paid',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            company_id INTEGER,
            FOREIGN KEY(customer_id) REFERENCES customer(id)
        )""")
        conn.execute("""INSERT INTO invoice_v4
            (id, invoice_no, customer_id, total_amount, discount_amount, tax_amount,
             grand_total, payment_mode, status, created_at, company_id)
            SELECT id, invoice_no, customer_id, total_amount, discount_amount, tax_amount,
                   grand_total, payment_mode, status, created_at, company_id
            FROM invoice""")
        conn.execute("DROP TABLE invoice")
        conn.execute("ALTER TABLE invoice_v4 RENAME TO invoice")
    else:
        # Constraint names are the PostgreSQL defaults from schema_postgres.sql.
        conn.execute("ALTER TABLE item DROP CONSTRAINT IF EXISTS item_code_key")
        conn.execute("ALTER TABLE invoice DROP CONSTRAINT IF EXISTS invoice_invoice_no_key")

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_item_company_code ON item(company_id, code)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_invoice_company_no ON invoice(company_id, invoice_no)")


def migrate() -> None:
    conn = get_connection()
    sqlite_backend = isinstance(conn, sqlite3.Connection)
    try:
        # SQLite requires foreign_keys to be disabled before a transaction for
        # a safe parent-table rebuild. Re-enable it after commit/rollback.
        if sqlite_backend:
            conn.execute("PRAGMA foreign_keys = OFF")
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
        if 2 not in versions:
            if "company_id" not in get_columns(conn, "license"):
                conn.execute("ALTER TABLE license ADD COLUMN company_id INTEGER")
            conn.execute("INSERT INTO schema_migration(version) VALUES (2)")
        if 3 not in versions:
            duplicates = conn.execute("""SELECT LOWER(username) AS normalized, COUNT(*) AS n
                FROM user_account GROUP BY LOWER(username) HAVING COUNT(*) > 1""").fetchall()
            if duplicates:
                names = ", ".join(row["normalized"] for row in duplicates[:5])
                raise RuntimeError(
                    "Cannot apply migration v3: usernames differ only by letter case "
                    f"({names}). Resolve duplicate accounts before retrying."
                )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_user_account_username_lower ON user_account (LOWER(username))")
            conn.execute("INSERT INTO schema_migration(version) VALUES (3)")
        if 4 not in versions:
            _scope_unique_constraints(conn, sqlite_backend)
            conn.execute("INSERT INTO schema_migration(version) VALUES (4)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if sqlite_backend:
            try:
                conn.execute("PRAGMA foreign_keys = ON")
            except Exception:
                pass
        conn.close()
