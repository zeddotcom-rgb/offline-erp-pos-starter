from dataclasses import dataclass
from typing import Optional


@dataclass
class Company:
    name: str
    gstin: Optional[str] = None
    upi_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    financial_year: Optional[str] = None


@dataclass
class Item:
    code: str
    name: str
    category: Optional[str] = None
    barcode: Optional[str] = None
    hsn_sac: Optional[str] = None
    purchase_price: float = 0.0
    sale_price: float = 0.0
    mrp: float = 0.0
    stock_qty: float = 0.0
    min_stock: float = 0.0
    max_stock: float = 0.0
    gst_rate: float = 0.0
