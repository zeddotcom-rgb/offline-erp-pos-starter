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
        self.assertEqual(versions, {1, 2, 3, 4})

    def test_v4_preserves_legacy_records_and_allows_company_scoped_codes(self):
        conn = database.get_connection()
        try:
            conn.execute("INSERT INTO company(name) VALUES ('Company A')")
            conn.execute("INSERT INTO company(name) VALUES ('Company B')")
            company_a = conn.execute("SELECT id FROM company WHERE name='Company A'").fetchone()["id"]
            company_b = conn.execute("SELECT id FROM company WHERE name='Company B'").fetchone()["id"]
            conn.execute("INSERT INTO item(code,name,stock_qty) VALUES ('DUP-1','Legacy Item',7)")
            item_id = conn.execute("SELECT id FROM item WHERE code='DUP-1'").fetchone()["id"]
            conn.execute("""INSERT INTO invoice(invoice_no, total_amount, grand_total)
                VALUES ('DUP-INV', 5, 5)""")
            invoice_id = conn.execute("SELECT id FROM invoice WHERE invoice_no='DUP-INV'").fetchone()["id"]
            conn.execute("""INSERT INTO invoice_item
                (invoice_id,item_id,quantity,rate,amount) VALUES (?, ?, 1, 5, 5)""",
                (invoice_id, item_id))
            conn.commit()
        finally:
            conn.close()

        migrate()
        conn = database.get_connection()
        try:
            item = conn.execute("SELECT id, stock_qty FROM item WHERE id=?", (item_id,)).fetchone()
            invoice = conn.execute("SELECT id, grand_total FROM invoice WHERE id=?", (invoice_id,)).fetchone()
            conn.execute("UPDATE item SET company_id=? WHERE id=?", (company_a, item_id))
            conn.execute("UPDATE invoice SET company_id=? WHERE id=?", (company_a, invoice_id))
            conn.execute("""INSERT INTO item(code,name,stock_qty,company_id)
                VALUES ('DUP-1','Company B Item',2,?)""", (company_b,))
            conn.execute("""INSERT INTO invoice(invoice_no,total_amount,grand_total,company_id)
                VALUES ('DUP-INV', 8, 8, ?)""", (company_b,))
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(item["id"], item_id)
        self.assertEqual(item["stock_qty"], 7)
        self.assertEqual(invoice["id"], invoice_id)
        self.assertEqual(invoice["grand_total"], 5)
        self.assertEqual(foreign_key_errors, [])

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
