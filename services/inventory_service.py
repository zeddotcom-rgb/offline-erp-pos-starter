"""Tenant-scoped inventory operations; all writes require an authorized session."""
from database import get_connection
from services.security_service import require_permission


def add_item(code, name, sale_price, purchase_price=0, stock_qty=0, category="General",
             barcode=None, gst_rate=0, session=None):
    actor = require_permission(session, "inventory.write")
    if not code or not str(name).strip():
        raise ValueError("Item code and name are required.")
    if float(sale_price) < 0 or float(purchase_price) < 0 or float(stock_qty) < 0:
        raise ValueError("Prices and opening stock cannot be negative.")
    conn = get_connection()
    try:
        cur = conn.execute("""INSERT INTO item
            (code, name, category, barcode, purchase_price, sale_price, stock_qty, gst_rate, company_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, name, category, barcode, purchase_price, sale_price, stock_qty, gst_rate, actor.company_id))
        item_id = int(cur.lastrowid)
        if float(stock_qty) > 0:
            conn.execute("""INSERT INTO stock_move
                (item_id, movement_type, quantity, reference_no, remarks, company_id)
                VALUES (?, 'opening', ?, 'OPENING', 'Opening stock', ?)""",
                (item_id, float(stock_qty), actor.company_id))
        conn.commit()
        return item_id
    finally:
        conn.close()


def get_item_by_code(code, session=None):
    actor = require_permission(session, "inventory.read")
    conn = get_connection()
    try:
        item = conn.execute("SELECT * FROM item WHERE code=? AND company_id=?", (code, actor.company_id)).fetchone()
        return dict(item) if item else None
    finally:
        conn.close()


def stock_report(session=None):
    actor = require_permission(session, "inventory.read")
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT id, code, name, stock_qty, sale_price FROM item
            WHERE is_active=1 AND company_id=? ORDER BY name""", (actor.company_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
