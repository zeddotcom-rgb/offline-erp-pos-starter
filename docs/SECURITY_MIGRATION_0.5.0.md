# Security and migration notes — TradeDesk Pro 0.5.0

## Back up before upgrading
Copy the database file (SQLite) or take a PostgreSQL backup before running migrations. Test the upgrade on a restored copy first.

## Migration policy
1. Run the application entry point; it initializes the selected database backend and applies versioned migrations.
2. Migration v1 adds nullable `company_id` fields to legacy business tables, adds the audit actor field, and creates setup state.
3. Migration v2 adds `company_id` to license records for databases that already applied the earlier v1.
4. Migration v3 creates a case-insensitive unique username index. If legacy accounts contain names that differ only by case, migration stops; resolve those accounts deliberately and retry.
5. Migration v4 rebuilds the SQLite item and invoice tables to replace global item-code/invoice-number uniqueness with company-scoped indexes. It preserves IDs and foreign-key references. PostgreSQL drops the original global constraints and creates the same tenant-scoped indexes.
6. Existing rows remain unscoped until the one-time setup transaction adopts them into the first company. This is explicit backfill, not inferred ownership.
7. Existing legacy user accounts are disabled because the application cannot verify their password format. Create the new Argon2 administrator in setup.
8. Inspect record counts, foreign-key integrity and company ownership after migration before returning to production use.

## Database backends
- SQLite: default for offline single-PC mode.
- PostgreSQL: set `DB_BACKEND=postgresql` and `DATABASE_URL` for LAN/server mode. A PostgreSQL 16 service integration test runs in GitHub Actions.

## Username policy
Usernames remain globally unique and case-insensitive because the current sign-in form accepts a username and password without a company selector. The migration refuses case-variant duplicate legacy usernames rather than guessing which account should own the login.
