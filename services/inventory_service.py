from database import get_connection


def add_item(code, name, sale_price, purchase_price=0, stock_qty=0, category="General", barcode=None, gst_rate=0):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO item(code, name, category, barcode, purchase_price, sale_price, stock_qty, gst_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (code, name, category, barcode, purchase_price, sale_price, stock_qty, gst_rate),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    finally:
        conn.close()


def get_item_by_code(code):
    conn = get_connection()
    item = conn.execute("SELECT * FROM item WHERE code = ?", (code,)).fetchone()
    conn.close()
    return dict(item) if item else None


def stock_report():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, code, name, stock_qty, sale_price FROM item WHERE is_active = 1 ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
