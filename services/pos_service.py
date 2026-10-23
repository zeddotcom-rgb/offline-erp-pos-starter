from database import get_connection


def ensure_stock(item_id: int, qty: float):
    conn = get_connection()
    item = conn.execute("SELECT stock_qty FROM item WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if item is None:
        raise ValueError("Item not found")
    if item["stock_qty"] < qty:
        raise ValueError(f"Not enough stock for item id {item_id}")
    return item["stock_qty"]


def create_invoice(invoice_no: str, customer_id: int, items: list, payment_mode: str = "cash"):
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        total_amount = 0
        tax_amount = 0
        discount_amount = 0

        for item_entry in items:
            item_id = item_entry["item_id"]
            qty = float(item_entry["qty"])
            rate = float(item_entry["rate"])
            discount = float(item_entry.get("discount", 0))
            tax_rate = float(item_entry.get("tax_rate", 0))

            item = conn.execute(
                "SELECT stock_qty, sale_price FROM item WHERE id = ?",
                (item_id,),
            ).fetchone()
            if not item:
                raise ValueError(f"Item {item_id} not found")
            if item["stock_qty"] < qty:
                raise ValueError(f"Insufficient stock for item {item_id}")

            line_total = (qty * rate) - discount
            total_amount += line_total
            tax_amount += line_total * (tax_rate / 100)
            discount_amount += discount

            conn.execute(
                "UPDATE item SET stock_qty = stock_qty - ? WHERE id = ?",
                (qty, item_id),
            )
            conn.execute(
                "INSERT INTO stock_move(item_id, movement_type, quantity, reference_no, remarks) VALUES (?, 'sale', ?, ?, ?)",
                (item_id, -qty, invoice_no, f"Invoice {invoice_no}"),
            )

        grand_total = total_amount + tax_amount - discount_amount

        conn.execute(
            """
            INSERT INTO invoice(invoice_no, customer_id, total_amount, discount_amount, tax_amount, grand_total, payment_mode, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'paid')
            """,
            (invoice_no, customer_id, total_amount, discount_amount, tax_amount, grand_total, payment_mode),
        )
        invoice_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        for item_entry in items:
            item_id = item_entry["item_id"]
            qty = float(item_entry["qty"])
            rate = float(item_entry["rate"])
            discount = float(item_entry.get("discount", 0))
            tax_rate = float(item_entry.get("tax_rate", 0))
            line_amount = (qty * rate) - discount
            line_tax = line_amount * (tax_rate / 100)
            conn.execute(
                """
                INSERT INTO invoice_item(invoice_id, item_id, quantity, rate, discount, tax_rate, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (invoice_id, item_id, qty, rate, discount, tax_rate, line_amount + line_tax),
            )

        conn.execute("COMMIT")
        return {"invoice_id": invoice_id, "grand_total": grand_total}
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
