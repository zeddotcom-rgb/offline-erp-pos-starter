"""Company-scoped user administration with permission checks and audit events."""
import json
from argon2 import PasswordHasher

from database import get_connection
from services.security_service import require_permission

_PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
ROLES = {"admin", "manager", "cashier", "inventory", "viewer"}


def list_users(session=None):
    actor = require_permission(session, "users.read")
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT id, username, role, branch, is_active, created_at
            FROM user_account WHERE company_id=? ORDER BY username""", (actor.company_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_user(username, password, role="cashier", branch="main", session=None):
    actor = require_permission(session, "users.write")
    username = str(username or "").strip()
    if len(username) < 3 or len(username) > 80:
        raise ValueError("Username must be between 3 and 80 characters.")
    if len(password or "") < 12:
        raise ValueError("Password must be at least 12 characters.")
    if role not in ROLES:
        raise ValueError("Unknown role.")
    password_hash = _PASSWORDS.hash(password)
    conn = get_connection()
    try:
        cur = conn.execute("""INSERT INTO user_account
            (username, password_hash, role, branch, is_active, company_id)
            VALUES (?, ?, ?, ?, 1, ?)""",
            (username, password_hash, role, branch or "main", actor.company_id))
        user_id = int(cur.lastrowid)
        conn.execute("""INSERT INTO audit_log(entity_type, entity_id, action, details, company_id, actor_id)
            VALUES ('user', ?, 'user_created', ?, ?, ?)""",
            (user_id, json.dumps({"username": username, "role": role}), actor.company_id, actor.user_id))
        conn.commit()
        return user_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def change_user_role(user_id, role, session=None):
    actor = require_permission(session, "users.write")
    if role not in ROLES:
        raise ValueError("Unknown role.")
    if int(user_id) == actor.user_id and role != "admin":
        raise ValueError("You cannot demote your own active administrator account.")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        target = conn.execute("SELECT id, role FROM user_account WHERE id=? AND company_id=?",
                              (int(user_id), actor.company_id)).fetchone()
        if not target:
            raise ValueError("User not found in this company.")
        if target["role"] == "admin" and role != "admin":
            count = conn.execute("SELECT COUNT(*) AS n FROM user_account WHERE company_id=? AND role='admin' AND is_active=1",
                                 (actor.company_id,)).fetchone()["n"]
            if count <= 1:
                raise ValueError("Cannot demote the last active administrator.")
        conn.execute("UPDATE user_account SET role=? WHERE id=? AND company_id=?",
                     (role, int(user_id), actor.company_id))
        conn.execute("""INSERT INTO audit_log(entity_type, entity_id, action, details, company_id, actor_id)
            VALUES ('user', ?, 'user_role_changed', ?, ?, ?)""",
            (int(user_id), json.dumps({"role": role}), actor.company_id, actor.user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deactivate_user(user_id, session=None):
    actor = require_permission(session, "users.write")
    if int(user_id) == actor.user_id:
        raise ValueError("You cannot deactivate your own signed-in account.")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        target = conn.execute("SELECT id, role FROM user_account WHERE id=? AND company_id=? AND is_active=1",
                              (int(user_id), actor.company_id)).fetchone()
        if not target:
            raise ValueError("Active user not found in this company.")
        if target["role"] == "admin":
            count = conn.execute("SELECT COUNT(*) AS n FROM user_account WHERE company_id=? AND role='admin' AND is_active=1",
                                 (actor.company_id,)).fetchone()["n"]
            if count <= 1:
                raise ValueError("Cannot deactivate the last active administrator.")
        conn.execute("UPDATE user_account SET is_active=0 WHERE id=? AND company_id=?",
                     (int(user_id), actor.company_id))
        conn.execute("""INSERT INTO audit_log(entity_type, entity_id, action, details, company_id, actor_id)
            VALUES ('user', ?, 'user_deactivated', '{}', ?, ?)""",
            (int(user_id), actor.company_id, actor.user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
