# TradeDesk Pro 0.5.0 security and migration notes

## Migration policy
1. Back up the SQLite database before upgrading.
2. Run `python -c "from database import init_db; from migrations import migrate; init_db(); migrate()"`.
3. Migration v1 adds nullable `company_id` columns and `actor_id` to legacy tables. It does not guess a tenant for existing business data.
4. On first launch, the setup wizard creates/updates the first company and atomically adopts rows with NULL `company_id` into that company. Existing legacy user accounts are disabled because this release cannot establish that their password hashes are trustworthy.
5. Create a new administrator using a unique password of at least 12 characters. Keep a tested database backup before upgrading production data.

## Verification status
The automated unit suite and Windows executable build are configured in GitHub Actions. A successful workflow run is required before treating either as verified. This repository currently has a SQLite-only database adapter; PostgreSQL verification is not supported until a PostgreSQL adapter and dialect-aware migrations are implemented. No executable is committed to source control.
