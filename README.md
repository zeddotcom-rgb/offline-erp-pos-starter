# TradeDesk Pro 0.5.0 — Security & Company Setup

Offline-first Windows desktop ERP/POS starter. This branch introduces a first-run company setup wizard, Argon2 administrator authentication, role permissions enforced by service methods, tenant-scoped inventory and invoices, audit events, and an idempotent SQLite schema migration.

## Requirements
- Python 3.11 or 3.12
- SQLite (bundled with Python)
- Packages in `requirements.txt`

## Run on Windows
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

On first launch, the setup wizard creates or adopts the first company and creates its administrator. Use a unique password of at least 12 characters. Existing unscoped business rows are assigned to the selected company in the same transaction; legacy user accounts are disabled because their password-hash formats cannot be trusted. Setup is marked complete atomically and cannot be run again through the application.

## Tests
```powershell
python -m unittest discover -s tests -v
```
GitHub Actions runs the unit suite on Python 3.11 and 3.12.

## Security and migration notes
- Passwords are stored as Argon2id hashes using `argon2-cffi`; plaintext passwords are never persisted.
- Built-in roles: `admin`, `manager`, `cashier`, `inventory`, and `viewer`.
- Service methods require an authenticated session and check permissions before writes.
- Migration v1 adds nullable `company_id` fields to legacy business tables. Existing rows are not guessed into a tenant until the one-time setup transaction explicitly backfills them.
- The included database adapter is currently SQLite-only. PostgreSQL compatibility and a Windows executable are not claimed as verified in this branch; those require a PostgreSQL driver/backend implementation and a Windows build runner.

## License
See [LICENSE](LICENSE).
