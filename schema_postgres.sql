CREATE TABLE IF NOT EXISTS company (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    gstin TEXT,
    upi_id TEXT,
    address TEXT,
    phone TEXT,
    email TEXT,
    financial_year TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_account (
    id BIGSERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'cashier',
    branch TEXT DEFAULT 'main',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS customer (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    gstin TEXT,
    credit_limit DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS supplier (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    gstin TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS item (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    barcode TEXT,
    hsn_sac TEXT,
    purchase_price DOUBLE PRECISION DEFAULT 0,
    sale_price DOUBLE PRECISION DEFAULT 0,
    mrp DOUBLE PRECISION DEFAULT 0,
    stock_qty DOUBLE PRECISION DEFAULT 0,
    min_stock DOUBLE PRECISION DEFAULT 0,
    max_stock DOUBLE PRECISION DEFAULT 0,
    gst_rate DOUBLE PRECISION DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS item_price (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL REFERENCES item(id),
    price_name TEXT NOT NULL DEFAULT 'default',
    price DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_move (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL REFERENCES item(id),
    movement_type TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    reference_no TEXT,
    remarks TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS invoice (
    id BIGSERIAL PRIMARY KEY,
    invoice_no TEXT UNIQUE NOT NULL,
    customer_id BIGINT REFERENCES customer(id),
    total_amount DOUBLE PRECISION NOT NULL,
    discount_amount DOUBLE PRECISION DEFAULT 0,
    tax_amount DOUBLE PRECISION DEFAULT 0,
    grand_total DOUBLE PRECISION NOT NULL,
    payment_mode TEXT,
    status TEXT DEFAULT 'paid',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS invoice_item (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoice(id),
    item_id BIGINT NOT NULL REFERENCES item(id),
    quantity DOUBLE PRECISION NOT NULL,
    rate DOUBLE PRECISION NOT NULL,
    discount DOUBLE PRECISION DEFAULT 0,
    tax_rate DOUBLE PRECISION DEFAULT 0,
    amount DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS license (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    edition TEXT NOT NULL,
    user_limit INTEGER NOT NULL DEFAULT 1,
    expiry_iso TEXT NOT NULL,
    machine_fingerprint TEXT NOT NULL,
    license_key TEXT NOT NULL,
    issued_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id BIGINT,
    action TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
