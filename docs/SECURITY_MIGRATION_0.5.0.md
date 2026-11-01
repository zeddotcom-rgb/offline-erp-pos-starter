# Security and migration notes — TradeDesk Pro 0.5.0

## Back up before upgrading
Copy the database file (SQLite) or take a PostgreSQL backup before running migrations. Test the upgrade on a restored copy first.

## Migration policy
1. Run the application entry point; it initializes the selected database backend and applies versioned migrations.
2. Migration v1 adds nullable `company_id` fields to legacy business tables, adds the audit actor field, and creates setup state.
3. Migration v2 adds `company_id` to license records for databases that already applied the earlier v1.
4. Existing rows remain unscoped until the one-time setup transaction adopts them into the first company. This is explicit backfill, not inferred ownership.
5. Existing legacy user accounts are disabled because the application cannot verify their password format. Create the new Argon2 administrator in setup.
6. Inspect record counts and company ownership after migration before returning to production use.

## Database backends
- SQLite: default for offline single-PC mode.
- PostgreSQL: set `DB_BACKEND=postgresql` and `DATABASE_URL` for LAN/server mode. A PostgreSQL 16 service integration test runs in GitHub Actions.

## Known release-review item
The original schema has globally unique item codes and invoice numbers. Although service reads and writes are company-filtered, duplicate item codes or invoice numbers across companies may still be rejected by those legacy constraints. Replace global uniqueness with tenant-scoped constraints in a dedicated, tested migration before promising unrestricted multi-company operation.
