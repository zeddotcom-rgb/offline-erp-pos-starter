import tempfile
import unittest
from pathlib import Path

import database
from migrations import migrate
from services.security_service import (
    AuthenticationError, AuthorizationError, SetupAlreadyCompleted, Session,
    authenticate, create_initial_setup, require_permission, setup_is_complete,
)
from services.inventory_service import add_item, stock_report
from services.pos_service import create_invoice
from services.party_service import create_customer, create_supplier, list_customers, list_suppliers
from services.user_service import create_user, change_user_role, deactivate_user, list_users


class SecurityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.temp.name) / "test.db"
        database.init_db()
        migrate()

    def tearDown(self):
        self.temp.cleanup()

    def setup_admin(self):
        return create_initial_setup(
            {"name": "Example Co", "address": "Test Road"},
            "adminuser", "Strong-password-123!"
        )

    def test_setup_is_one_time_and_creates_argon2_admin(self):
        self.assertFalse(setup_is_complete())
        session = self.setup_admin()
        self.assertEqual(session.role, "admin")
        self.assertTrue(setup_is_complete())
        with self.assertRaises(SetupAlreadyCompleted):
            self.setup_admin()
        conn = database.get_connection()
        stored = conn.execute("SELECT password_hash FROM user_account WHERE username='adminuser'").fetchone()["password_hash"]
        conn.close()
        self.assertTrue(stored.startswith("$argon2"))

    def test_authentication_and_failed_login(self):
        self.setup_admin()
        session = authenticate("adminuser", "Strong-password-123!")
        self.assertEqual(session.company_id, 1)
        with self.assertRaises(AuthenticationError):
            authenticate("adminuser", "wrong-password")
        conn = database.get_connection()
        count = conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE action='login_failed'").fetchone()["n"]
        conn.close()
        self.assertEqual(count, 1)

    def test_permissions_are_enforced(self):
        self.setup_admin()
        conn = database.get_connection()
        conn.execute("UPDATE user_account SET role='cashier' WHERE username='adminuser'")
        conn.commit()
        conn.close()
        session = authenticate("adminuser", "Strong-password-123!")
        self.assertEqual(require_permission(session, "pos.sell").role, "cashier")
        with self.assertRaises(AuthorizationError):
            require_permission(session, "users.write")

    def test_forged_admin_role_is_not_trusted(self):
        self.setup_admin()
        conn = database.get_connection()
        conn.execute("UPDATE user_account SET role='cashier' WHERE username='adminuser'")
        conn.commit()
        conn.close()
        forged = Session(1, "adminuser", "admin", 1)
        with self.assertRaises(AuthorizationError):
            require_permission(forged, "users.write")

    def test_inventory_and_pos_are_company_scoped(self):
        session = self.setup_admin()
        add_item("OWN-1", "Own Item", 10, stock_qty=5, session=session)
        conn = database.get_connection()
        conn.execute("INSERT INTO company(name) VALUES ('Other Co')")
        other_company = conn.execute("SELECT id FROM company WHERE name='Other Co'").fetchone()["id"]
        conn.execute("INSERT INTO item(code,name,sale_price,stock_qty,company_id) VALUES ('OTHER-1','Other Item',1,20,?)", (other_company,))
        other_item_id = conn.execute("SELECT id FROM item WHERE code='OTHER-1'").fetchone()["id"]
        conn.commit()
        conn.close()
        self.assertEqual([item["code"] for item in stock_report(session)], ["OWN-1"])
        with self.assertRaises(ValueError):
            create_invoice("CROSS-TENANT", None, [{"item_id": other_item_id, "qty": 1, "rate": 1}], session=session)

    def test_customer_and_supplier_lists_are_company_scoped(self):
        session = self.setup_admin()
        create_customer("Own Customer", phone="111", session=session)
        create_supplier("Own Supplier", phone="222", session=session)
        conn = database.get_connection()
        other_company = conn.execute("INSERT INTO company(name) VALUES ('Other Tenant')").lastrowid
        conn.execute("INSERT INTO customer(name, company_id) VALUES ('Foreign Customer', ?)", (other_company,))
        conn.execute("INSERT INTO supplier(name, company_id) VALUES ('Foreign Supplier', ?)", (other_company,))
        conn.commit()
        conn.close()
        self.assertEqual([r["name"] for r in list_customers(session)], ["Own Customer"])
        self.assertEqual([r["name"] for r in list_suppliers(session)], ["Own Supplier"])

    def test_user_administration_is_authorized_audited_and_company_scoped(self):
        admin = self.setup_admin()
        user_id = create_user("cashier1", "Strong-password-456!", role="cashier", session=admin)
        users = list_users(admin)
        self.assertIn("cashier1", [user["username"] for user in users])
        self.assertNotIn("password_hash", users[0])
        change_user_role(user_id, "viewer", session=admin)
        conn = database.get_connection()
        role = conn.execute("SELECT role FROM user_account WHERE id=?", (user_id,)).fetchone()["role"]
        conn.close()
        self.assertEqual(role, "viewer")
        deactivate_user(user_id, session=admin)
        with self.assertRaises(AuthenticationError):
            authenticate("cashier1", "Strong-password-456!")
        with self.assertRaises(ValueError):
            deactivate_user(admin.user_id, session=admin)
        conn = database.get_connection()
        actions = {r["action"] for r in conn.execute(
            "SELECT action FROM audit_log WHERE company_id=?", (admin.company_id,)
        ).fetchall()}
        conn.close()
        self.assertTrue({"user_created", "user_role_changed", "user_deactivated"}.issubset(actions))

    def test_legacy_records_are_backfilled_during_setup(self):
        conn = database.get_connection()
        conn.execute("INSERT INTO item(code,name,stock_qty) VALUES ('OLD-1','Legacy Item',7)")
        conn.commit()
        conn.close()
        self.setup_admin()
        conn = database.get_connection()
        row = conn.execute("SELECT company_id, stock_qty FROM item WHERE code='OLD-1'").fetchone()
        conn.close()
        self.assertEqual(row["company_id"], 1)
        self.assertEqual(row["stock_qty"], 7)


if __name__ == "__main__":
    unittest.main()
