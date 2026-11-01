"""Company-scoped customer and supplier service methods."""
from database import get_connection
from services.security_service import require_permission


def create_customer(name, phone=None, email=None, gstin=None, credit_limit=0, session=None):
    actor = require_permission(session, "customers.write")
    name = str(name or "").strip()
    if not name:
        raise ValueError("Customer name is required.")
    if float(credit_limit) < 0:
        raise ValueError("Credit limit cannot be negative.")
    conn = get_connection()
    try:
        cur = conn.execute("""INSERT INTO customer
            (name, phone, email, gstin, credit_limit, company_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (name, phone, email, gstin, float(credit_limit), actor.company_id))
        conn.commit()
        return int(cur.lastrowid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_customers(session=None):
    actor = require_permission(session, "customers.read")
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT id, name, phone, email, gstin, credit_limit
            FROM customer WHERE company_id=? ORDER BY name""", (actor.company_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_supplier(name, phone=None, email=None, gstin=None, session=None):
    actor = require_permission(session, "inventory.write")
    name = str(name or "").strip()
    if not name:
        raise ValueError("Supplier name is required.")
    conn = get_connection()
    try:
        cur = conn.execute("""INSERT INTO supplier
            (name, phone, email, gstin, company_id)
            VALUES (?, ?, ?, ?, ?)""", (name, phone, email, gstin, actor.company_id))
        conn.commit()
        return int(cur.lastrowid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_suppliers(session=None):
    actor = require_permission(session, "inventory.read")
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT id, name, phone, email, gstin
            FROM supplier WHERE company_id=? ORDER BY name""", (actor.company_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
