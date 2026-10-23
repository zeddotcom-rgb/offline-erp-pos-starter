import json
import hashlib
import base64
import platform
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from config import LICENSE_PUBLIC_KEY_PATH, LICENSE_PRIVATE_KEY_PATH


def generate_machine_fingerprint():
    raw = platform.node() + "|" + platform.system() + "|" + platform.release()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_keys():
    if not LICENSE_PRIVATE_KEY_PATH.exists() or not LICENSE_PUBLIC_KEY_PATH.exists():
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        LICENSE_PRIVATE_KEY_PATH.write_bytes(priv_pem)
        LICENSE_PUBLIC_KEY_PATH.write_bytes(pub_pem)


def load_private_key():
    ensure_keys()
    with open(LICENSE_PRIVATE_KEY_PATH, "rb") as f:
        return load_pem_private_key(f.read(), password=None)


def load_public_key():
    ensure_keys()
    with open(LICENSE_PUBLIC_KEY_PATH, "rb") as f:
        return load_pem_public_key(f.read())


def sign_license_payload(payload: Dict[str, Any]) -> str:
    priv = load_private_key()
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = priv.sign(
        payload_json,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("ascii")


def verify_license_payload(payload: Dict[str, Any], signature_b64: str) -> bool:
    try:
        pub = load_public_key()
        sig = base64.b64decode(signature_b64.encode("ascii"))
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        pub.verify(sig, payload_json, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def build_license(customer_name: str, edition: str, user_limit: int, expiry_days: int, machine_fingerprint: str):
    payload = {
        "customer_name": customer_name,
        "edition": edition,
        "user_limit": user_limit,
        "machine_fingerprint": machine_fingerprint,
        "expiry_iso": (datetime.utcnow() + timedelta(days=expiry_days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issued_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "license_id": str(uuid.uuid4()),
    }
    payload["signature"] = sign_license_payload(payload)
    return payload


def is_license_valid(license_data: Dict[str, Any], machine_fingerprint: str) -> bool:
    if not license_data.get("signature"):
        return False
    if license_data.get("machine_fingerprint") != machine_fingerprint:
        return False

    payload = {k: v for k, v in license_data.items() if k != "signature"}
    if not verify_license_payload(payload, license_data["signature"]):
        return False

    expiry = datetime.strptime(license_data["expiry_iso"], "%Y-%m-%dT%H:%M:%SZ")
    if datetime.utcnow() > expiry:
        return False

    return True
