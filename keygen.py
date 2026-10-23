import argparse
import json
from pathlib import Path

from services.licensing import build_license, generate_machine_fingerprint


def main():
    parser = argparse.ArgumentParser(description="Offline ERP license key generator")
    parser.add_argument("--customer", required=True)
    parser.add_argument("--edition", required=True, choices=["starter", "professional", "enterprise"])
    parser.add_argument("--users", type=int, default=1)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--output", default="license.json")
    args = parser.parse_args()

    machine_fp = generate_machine_fingerprint()
    license = build_license(
        customer_name=args.customer,
        edition=args.edition,
        user_limit=args.users,
        expiry_days=args.days,
        machine_fingerprint=machine_fp,
    )

    out_path = Path(args.output)
    out_path.write_text(json.dumps(license, indent=2), encoding="utf-8")
    print(f"License saved to {out_path}")
    print(f"Machine fingerprint: {machine_fp}")
    print("Use this file in the app to validate the license.")


if __name__ == "__main__":
    main()
