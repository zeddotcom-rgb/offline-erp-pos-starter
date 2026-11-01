# TradeDesk Pro 0.5.0 — Security & Company Setup

Offline-first Windows desktop ERP/POS starter with a selectable local SQLite or shared PostgreSQL database backend.

## Requirements
- Python 3.11 or 3.12
- SQLite (included with Python) for offline/single-PC use
- PostgreSQL 14+ for shared LAN/server mode
- Packages in `requirements.txt`

## Run with SQLite on Windows
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

## Configure PostgreSQL for LAN mode
Create a dedicated PostgreSQL database and application user, then set these environment variables before launching the application:

```powershell
$env:DB_BACKEND = "postgresql"
$env:DATABASE_URL = "postgresql://tradedesk:YOUR_PASSWORD@SERVER_HOST:5432/tradedesk"
python app.py
```

Do not commit database credentials to source control. Restrict PostgreSQL network access to trusted LAN clients and use a strong database password. The database user should have access only to the application database.

On first launch, the setup wizard creates or adopts the first company and creates its administrator. Use a unique password of at least 12 characters. Existing unscoped business rows are assigned to the selected company in the same transaction; legacy user accounts are disabled because their password-hash formats cannot be trusted. Setup is marked complete atomically and cannot be run again through the application.

## Tests
```powershell
python -m unittest discover -s tests -v
```
GitHub Actions runs the SQLite unit suite on Python 3.11 and 3.12 and a PostgreSQL integration test against PostgreSQL 16. The integration test is skipped locally unless `TEST_DATABASE_URL` is set.

## Security and migration notes
- Passwords are stored as Argon2id hashes using `argon2-cffi`; plaintext passwords are never persisted.
- Built-in roles: `admin`, `manager`, `cashier`, `inventory`, and `viewer`.
- Authorization reloads role, active status, and company membership from the database at each service permission check.
- Inventory, POS, customer, and supplier service methods filter data by the authenticated company.
- Versioned migrations add nullable `company_id` fields. Existing rows are not assigned to a tenant until one-time setup explicitly backfills them. Migration v4 rebuilds the SQLite item and invoice tables while preserving IDs and foreign-key references, then replaces global item-code and invoice-number uniqueness with company-scoped unique indexes.
- Legacy user accounts are disabled during setup. Back up the database before upgrading and verify the migrated data before using it in production.
- Usernames remain globally unique and case-insensitive because login is username-only (there is no company selector at sign-in). Migration v3 detects legacy case-variant duplicate usernames and stops with an actionable error rather than silently choosing an account.

## License-key provisioning (release gate)
The application fails closed when the issuer's `public_key.pem` is missing; it never creates a signing key during license verification. Before a commercial release:

1. On a trusted vendor-only machine, generate the keypair once with `python keygen.py --customer "Key Setup" --edition professional --generate-keypair --machine-fingerprint "PLACEHOLDER"` only after confirming the command's issuer-side use. Do not issue the placeholder license.
2. Keep `private_key.pem` offline, access-controlled and backed up. Never commit or distribute it.
3. Provision the matching `public_key.pem` alongside the Windows executable (or set `TRADEDESK_LICENSE_PUBLIC_KEY` to its path).
4. Issue each customer's license using their supplied machine fingerprint with `--machine-fingerprint`.

No production public key is committed in this repository yet, so the CI executable artifact is a build/QA artifact and will not validate production licenses until the matching vendor public key is provisioned. The app's data and license files are stored in a persistent user-writable data directory when frozen; paths can be overridden with `TRADEDESK_DATA_DIR`, `TRADEDESK_DB_PATH`, and `TRADEDESK_LICENSE_FILE`.

## Windows executable
The Windows workflow builds a one-file executable and uploads it as a GitHub Actions artifact. Use the workflow run's artifact download rather than treating a source ZIP as the executable.

## License
See [LICENSE](LICENSE).
