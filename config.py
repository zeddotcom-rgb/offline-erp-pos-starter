import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "erp.db"
LICENSE_PUBLIC_KEY_PATH = BASE_DIR / "public_key.pem"
LICENSE_PRIVATE_KEY_PATH = BASE_DIR / "private_key.pem"

EDITION_LIMITS = {
    "starter": {"users": 1, "items": 500, "bills": 10000},
    "professional": {"users": 5, "items": 50000, "bills": 999999},
    "enterprise": {"users": 100, "items": 200000, "bills": 999999},
}
