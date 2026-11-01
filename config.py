"""Application paths and local/shared database configuration."""
import os
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else SOURCE_DIR

_default_data_dir = (
    Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "TradeDeskPro"
    if FROZEN else SOURCE_DIR
)
DATA_DIR = Path(os.environ.get("TRADEDESK_DATA_DIR", str(_default_data_dir))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("TRADEDESK_DB_PATH", str(DATA_DIR / "erp.db"))).expanduser()
# The verifier reads only a public key. Provision the vendor's public_key.pem next
# to the executable, or override the path with TRADEDESK_LICENSE_PUBLIC_KEY.
_embedded_public_key = Path(getattr(sys, "_MEIPASS", str(APP_DIR))) / "public_key.pem"
_default_public_key = _embedded_public_key if _embedded_public_key.is_file() else APP_DIR / "public_key.pem"
LICENSE_PUBLIC_KEY_PATH = Path(
    os.environ.get("TRADEDESK_LICENSE_PUBLIC_KEY", str(_default_public_key))
).expanduser()
# The private key is only for the separate license-issuer tool and is never needed
# by the customer application to validate a license.
LICENSE_PRIVATE_KEY_PATH = Path(
    os.environ.get("TRADEDESK_LICENSE_PRIVATE_KEY", str(DATA_DIR / "private_key.pem"))
).expanduser()
LICENSE_FILE_PATH = Path(
    os.environ.get("TRADEDESK_LICENSE_FILE", str(DATA_DIR / "license.json"))
).expanduser()

EDITION_LIMITS = {
    "starter": {"users": 1, "items": 500, "bills": 10000},
    "professional": {"users": 5, "items": 50000, "bills": 999999},
    "enterprise": {"users": 100, "items": 200000, "bills": 999999},
}
