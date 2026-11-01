"""Real PostgreSQL integration tests; skipped unless TEST_DATABASE_URL is configured."""
import os
import unittest
import uuid

TEST_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_URL, "TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped")
class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls._old_env = {key: os.environ.get(key) for key in ("DB_BACKEND", "DATABASE_URL", "PGSCHEMA")}
        cls.schema = "tradedesk_it_" + uuid.uuid4().hex[:10]
        with psycopg.connect(TEST_URL) as conn:
            conn.execute(f'CREATE SCHEMA "{cls.schema}"')
        os.environ["DB_BACKEND"] = "postgresql"
        os.environ["DATABASE_URL"] = TEST_URL
        os.environ["PGSCHEMA"] = cls.schema

        import database
        from migrations import migrate
        database.init_db()
        migrate()

    @classmethod
    def tearDownClass(cls):
        import psycopg
        with psycopg.connect(TEST_URL) as conn:
            conn.execute(f'DROP SCHEMA IF EXISTS "{cls.schema}" CASCADE')
        for key, value in cls._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_setup_inventory_invoice_and_audit_on_postgresql(self):
        from database import get_connection
        from services.security_service import authenticate, create_initial_setup
        from services.inventory_service import add_item, stock_report
        from services.pos_service import create_invoice
        from services.party_service import create_customer, create_supplier, list_customers, list_suppliers
        from services.user_service import create_user, list_users

        session = create_initial_setup({"name": "PostgreSQL Integration Co"}, "pgadmin", "Postgres-test-password-1!")
        self.assertEqual(authenticate("PGADMIN", "Postgres-test-password-1!").company_id, session.company_id)
        item_id = add_item("PG-1", "PG Item", 12.5, stock_qty=4, session=session)
        self.assertEqual(stock_report(session)[0]["id"], item_id)
        create_customer("PG Customer", session=session)
        create_supplier("PG Supplier", session=session)
        create_user("pgcashier", "Postgres-cashier-password-1!", role="cashier", session=session)
        self.assertEqual([row["name"] for row in list_customers(session)], ["PG Customer"])
        self.assertEqual([row["name"] for row in list_suppliers(session)], ["PG Supplier"])
        self.assertIn("pgcashier", [row["username"] for row in list_users(session)])
        invoice = create_invoice("PG-INV-1", None, [{"item_id": item_id, "qty": 1, "rate": 12.5}], session=session)
        self.assertAlmostEqual(invoice["grand_total"], 12.5)
        conn = get_connection()
        try:
            other_company = conn.execute("INSERT INTO company(name) VALUES ('Other PG Co')").lastrowid
            conn.execute("""INSERT INTO item(code,name,stock_qty,company_id)
                VALUES ('PG-1','Same Code, Other Tenant',2,?)""", (other_company,))
            conn.execute("""INSERT INTO invoice(invoice_no,total_amount,grand_total,company_id)
                VALUES ('PG-INV-1', 2, 2, ?)""", (other_company,))
            audit_count = conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE company_id=?", (session.company_id,)).fetchone()["n"]
            self.assertGreaterEqual(audit_count, 6)
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
