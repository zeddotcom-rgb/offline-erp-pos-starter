import tempfile
import unittest
from pathlib import Path

import database
from migrations import migrate


class MigrationUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "legacy.db"
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_v2_adds_license_company_id_to_existing_v1_database(self):
        conn = database.get_connection()
        try:
            # Simulate a database that already applied the original v1 migration,
            # before the license table was added to the tenant-scoped table list.
            for table in (
                "user_account", "customer", "supplier", "item", "item_price",
                "stock_move", "invoice", "invoice_item", "audit_log",
            ):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN company_id INTEGER")
            conn.execute("ALTER TABLE audit_log ADD COLUMN actor_id INTEGER")
            conn.execute("""CREATE TABLE schema_migration (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("INSERT INTO schema_migration(version) VALUES (1)")
            conn.execute("""CREATE TABLE setup_state (
                id INTEGER PRIMARY KEY CHECK (id=1),
                setup_completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT
            )""")
            conn.commit()
        finally:
            conn.close()

        migrate()
        conn = database.get_connection()
        try:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(license)").fetchall()}
            versions = {row["version"] for row in conn.execute("SELECT version FROM schema_migration").fetchall()}
        finally:
            conn.close()
        self.assertIn("company_id", columns)
        self.assertEqual(versions, {1, 2, 3})

    def test_v3_refuses_case_ambiguous_usernames(self):
        conn = database.get_connection()
        try:
            conn.execute("INSERT INTO user_account(username, password_hash) VALUES ('Alex', 'legacy')")
            conn.execute("INSERT INTO user_account(username, password_hash) VALUES ('alex', 'legacy')")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(RuntimeError, "differ only by letter case"):
            migrate()




if __name__ == "__main__":
    unittest.main()
