"""Vendor-side license issuer. Keep the private key off customer machines."""
import argparse
import json
from pathlib import Path

from config import LICENSE_FILE_PATH
from services.licensing import (
    build_license, ensure_keys, generate_machine_fingerprint,
)


def main():
    parser = argparse.ArgumentParser(description="Offline ERP license issuer (vendor-only)")
    parser.add_argument("--customer", required=True)
    parser.add_argument("--edition", required=True, choices=["starter", "professional", "enterprise"])
    parser.add_argument("--users", type=int, default=1)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--machine-fingerprint", help="Customer machine fingerprint; defaults to this machine")
    parser.add_argument("--output", default=str(LICENSE_FILE_PATH))
    parser.add_argument(
        "--generate-keypair", action="store_true",
        help="Explicitly generate a new RSA keypair only when neither key file exists",
    )
    args = parser.parse_args()

    if args.generate_keypair:
        ensure_keys()
        print("Keypair ready. Keep private_key.pem offline and secret; distribute only public_key.pem.")
    machine_fp = args.machine_fingerprint or generate_machine_fingerprint()
    try:
        license_data = build_license(
            customer_name=args.customer,
            edition=args.edition,
            user_limit=args.users,
            expiry_days=args.days,
            machine_fingerprint=machine_fp,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(license_data, indent=2), encoding="utf-8")
    print(f"License saved to {out_path}")
    print(f"Machine fingerprint: {machine_fp}")
    print("Distribute the license file and public key only. Never distribute private_key.pem.")


if __name__ == "__main__":
    main()
