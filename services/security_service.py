"""Authentication, authorization, first-run setup and audit services for TradeDesk Pro 0.5.0."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from database import get_connection, get_columns, table_exists

_PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
ROLE_PERMISSIONS = {
    "admin": {"*"},
    "manager": {"inventory.read", "inventory.write", "pos.read", "pos.sell", "customers.read", "customers.write", "reports.read", "users.read"},
    "cashier": {"inventory.read", "pos.read", "pos.sell", "customers.read"},
    "inventory": {"inventory.read", "inventory.write", "reports.read"},
    "viewer": {"inventory.read", "pos.read", "customers.read", "reports.read"},
}


class AuthenticationError(Exception):
    """Raised when credentials are invalid or an account is disabled."""


class AuthorizationError(PermissionError):
    """Raised when a user lacks a required permission."""


class SetupAlreadyCompleted(RuntimeError):
    """Raised when one-time company setup has already been completed."""


@dataclass(frozen=True)
class Session:
    user_id: int
    username: str
    role: str
    company_id: int

    def as_dict(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "username": self.username, "role": self.role, "company_id": self.company_id}


def setup_is_complete() -> bool:
    conn = get_connection()
    try:
        if not table_exists(conn, "setup_state"):
            return False
        row = conn.execute("SELECT setup_completed FROM setup_state WHERE id = 1").fetchone()
        return bool(row and row["setup_completed"])
    finally:
        conn.close()


def create_initial_setup(company: dict[str, str], username: str, password: str) -> Session:
    """Create/adopt a company and its first admin in one transaction.

    Existing unscoped business records are explicitly adopted by this company.
    Legacy accounts are disabled rather than silently trusted with unknown hash formats.
    """
    company_name = (company.get("name") or "").strip()
    username = username.strip()
    if not company_name:
        raise ValueError("Company name is required.")
    if len(username) < 3 or len(username) > 80:
        raise ValueError("Username must be between 3 and 80 characters.")
    if len(password) < 12:
        raise ValueError("Administrator password must be at least 12 characters.")
    password_hash = _PASSWORDS.hash(password)

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""CREATE TABLE IF NOT EXISTS setup_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            setup_completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT
        )""")
        state = conn.execute("SELECT setup_completed FROM setup_state WHERE id = 1").fetchone()
        if state and state["setup_completed"]:
            raise SetupAlreadyCompleted("Initial setup has already been completed.")

        existing = conn.execute("SELECT id FROM company ORDER BY id LIMIT 1").fetchone()
        values = (
            company_name, company.get("gstin") or None, company.get("upi_id") or None,
            company.get("address") or None, company.get("phone") or None,
            company.get("email") or None, company.get("financial_year") or None,
        )
        if existing:
            company_id = int(existing["id"])
            conn.execute("""UPDATE company SET name=?, gstin=?, upi_id=?, address=?, phone=?,
                email=?, financial_year=? WHERE id=?""", (*values, company_id))
        else:
            cur = conn.execute("""INSERT INTO company
                (name, gstin, upi_id, address, phone, email, financial_year)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", values)
            company_id = int(cur.lastrowid)

        # Legacy rows remain intact; they are assigned to the company explicitly during setup.
        for table in ("customer", "supplier", "item", "item_price", "stock_move", "invoice", "invoice_item", "audit_log"):
            cols = get_columns(conn, table)
            if "company_id" in cols:
                conn.execute(f"UPDATE {table} SET company_id=? WHERE company_id IS NULL", (company_id,))
        if "company_id" in get_columns(conn, "user_account"):
            conn.execute("UPDATE user_account SET is_active=0, company_id=? WHERE company_id IS NULL", (company_id,))
        else:
            conn.execute("UPDATE user_account SET is_active=0")

        cur = conn.execute("""INSERT INTO user_account
            (username, password_hash, role, branch, is_active, company_id)
            VALUES (?, ?, 'admin', 'main', 1, ?)""", (username, password_hash, company_id))
        user_id = int(cur.lastrowid)
        conn.execute("""INSERT INTO setup_state(id, setup_completed, completed_at)
            VALUES (1, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET setup_completed=1, completed_at=CURRENT_TIMESTAMP""")
        conn.execute("""INSERT INTO audit_log(entity_type, entity_id, action, details, company_id, actor_id)
            VALUES ('security', ?, 'initial_setup_completed', ?, ?, ?)""",
            (user_id, json.dumps({"company_id": company_id, "username": username}), company_id, user_id))
        conn.commit()
        return Session(user_id, username, "admin", company_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def authenticate(username: str, password: str) -> Session:
    conn = get_connection()
    try:
        row = conn.execute("""SELECT id, username, password_hash, role, company_id, is_active
            FROM user_account WHERE username = ? COLLATE NOCASE""", (username.strip(),)).fetchone()
        if not row or not row["is_active"] or not row["company_id"]:
            _audit_login_failure(conn, username)
            conn.commit()
            raise AuthenticationError("Invalid username or password.")
        try:
            valid = _PASSWORDS.verify(row["password_hash"], password)
        except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
            valid = False
        if not valid:
            _audit_login_failure(conn, username)
            conn.commit()
            raise AuthenticationError("Invalid username or password.")
        if _PASSWORDS.check_needs_rehash(row["password_hash"]):
            conn.execute("UPDATE user_account SET password_hash=? WHERE id=?", (_PASSWORDS.hash(password), row["id"]))
        conn.execute("""INSERT INTO audit_log(entity_type, entity_id, action, details, company_id, actor_id)
            VALUES ('security', ?, 'login_success', ?, ?, ?)""",
            (row["id"], json.dumps({"username": row["username"]}), row["company_id"], row["id"]))
        conn.commit()
        return Session(int(row["id"]), row["username"], row["role"], int(row["company_id"]))
    finally:
        conn.close()


def _audit_login_failure(conn, username: str) -> None:
    conn.execute("""INSERT INTO audit_log(entity_type, action, details)
        VALUES ('security', 'login_failed', ?)""", (json.dumps({"username": username[:80]}),))


def require_permission(session: Session | dict[str, Any] | None, permission: str) -> Session:
    if session is None:
        raise AuthorizationError("An authenticated session is required.")
    if isinstance(session, dict):
        try:
            session = Session(int(session["user_id"]), str(session["username"]), str(session["role"]), int(session["company_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthorizationError("Invalid session context.") from exc
    # Treat the caller's session as an identifier, not as trusted authority.
    # Reload role, active state, and tenant membership from the database on every
    # service authorization check so a forged/stale in-memory role cannot grant access.
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT username, role, company_id, is_active FROM user_account WHERE id=?",
            (session.user_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row["is_active"] or not row["company_id"]:
        raise AuthorizationError("User is inactive or has no company membership.")
    if int(row["company_id"]) != session.company_id:
        raise AuthorizationError("Session company does not match the user's company.")
    session = Session(session.user_id, row["username"], row["role"], int(row["company_id"]))
    allowed = ROLE_PERMISSIONS.get(session.role, set())
    if "*" not in allowed and permission not in allowed:
        raise AuthorizationError(f"Role '{session.role}' does not have permission '{permission}'.")
    return session


def audit_event(session: Session | dict[str, Any], action: str, entity_type: str,
                entity_id: int | None = None, details: dict[str, Any] | None = None) -> None:
    actor = require_permission(session, "audit.write") if isinstance(session, Session) and session.role != "admin" else session
    if isinstance(actor, dict):
        actor_id, company_id = int(actor["user_id"]), int(actor["company_id"])
    else:
        actor_id, company_id = actor.user_id, actor.company_id
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO audit_log(entity_type, entity_id, action, details, company_id, actor_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (entity_type, entity_id, action, json.dumps(details or {}, sort_keys=True), company_id, actor_id))
        conn.commit()
    finally:
        conn.close()
