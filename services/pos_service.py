"""Tenant-scoped POS operations with service-layer authorization."""
from database import get_connection
from services.security_service import require_permission, audit_event


def ensure_stock(item_id: int, qty: float, session=None):
    actor = require_permission(session, "inventory.read")
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero.")
    conn = get_connection()
    try:
        item = conn.execute("SELECT stock_qty FROM item WHERE id=? AND company_id=?", (item_id, actor.company_id)).fetchone()
        if item is None:
            raise ValueError("Item not found in this company.")
        if item["stock_qty"] < qty:
            raise ValueError(f"Not enough stock for item id {item_id}")
        return item["stock_qty"]
    finally:
        conn.close()


def create_invoice(invoice_no: str, customer_id: int | None, items: list,
                   payment_mode: str = "cash", session=None):
    actor = require_permission(session, "pos.sell")
    if not items:
        raise ValueError("Invoice must contain at least one item.")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        total_amount = tax_amount = discount_amount = 0.0
        if customer_id is not None:
            customer = conn.execute("SELECT id FROM customer WHERE id=? AND company_id=?",
                                     (customer_id, actor.company_id)).fetchone()
            if not customer:
                raise ValueError("Customer not found in this company.")
        for entry in items:
            item_id = int(entry["item_id"])
            qty, rate = float(entry["qty"]), float(entry["rate"])
            discount, tax_rate = float(entry.get("discount", 0)), float(entry.get("tax_rate", 0))
            if qty <= 0 or rate < 0 or discount < 0 or tax_rate < 0 or discount > qty * rate:
                raise ValueError("Invalid quantity, rate, discount, or tax.")
            item = conn.execute("SELECT stock_qty FROM item WHERE id=? AND company_id=? AND is_active=1",
                                (item_id, actor.company_id)).fetchone()
            if not item:
                raise ValueError(f"Item {item_id} not found in this company.")
            if item["stock_qty"] < qty:
                raise ValueError(f"Insufficient stock for item {item_id}.")
            line_net = qty * rate - discount
            total_amount += line_net
            tax_amount += line_net * tax_rate / 100
            discount_amount += discount
            conn.execute("UPDATE item SET stock_qty=stock_qty-? WHERE id=? AND company_id=?",
                         (qty, item_id, actor.company_id))
            conn.execute("""INSERT INTO stock_move
                (item_id, movement_type, quantity, reference_no, remarks, company_id)
                VALUES (?, 'sale', ?, ?, ?, ?)""",
                (item_id, -qty, invoice_no, f"Invoice {invoice_no}", actor.company_id))
        grand_total = total_amount + tax_amount
        cur = conn.execute("""INSERT INTO invoice
            (invoice_no, customer_id, total_amount, discount_amount, tax_amount, grand_total,
             payment_mode, status, company_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'paid', ?)""",
            (invoice_no, customer_id, total_amount, discount_amount, tax_amount, grand_total,
             payment_mode, actor.company_id))
        invoice_id = int(cur.lastrowid)
        for entry in items:
            qty, rate = float(entry["qty"]), float(entry["rate"])
            discount, tax_rate = float(entry.get("discount", 0)), float(entry.get("tax_rate", 0))
            line_amount = qty * rate - discount
            amount = line_amount + line_amount * tax_rate / 100
            conn.execute("""INSERT INTO invoice_item
                (invoice_id, item_id, quantity, rate, discount, tax_rate, amount, company_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (invoice_id, int(entry["item_id"]), qty, rate, discount, tax_rate, amount, actor.company_id))
        conn.execute("""INSERT INTO audit_log(entity_type, entity_id, action, details, company_id, actor_id)
            VALUES ('invoice', ?, 'invoice_created', ?, ?, ?)""",
            (invoice_id, f'{{"invoice_no":"{invoice_no}","grand_total":{grand_total:.2f}}}',
             actor.company_id, actor.user_id))
        conn.commit()
        return {"invoice_id": invoice_id, "grand_total": grand_total}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
