"""MCP inbound bearer token management.

Tokens created by admins (CLI / future UI). Plaintext shown once at creation;
SHA-256 hash stored. Verification compares provided plaintext's hash to stored.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mcp_access_token import McpAccessToken


def _hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def create_token(
    db: Session, user_id: str, name: str,
    scopes: dict, expires_in_days: Optional[int] = None,
) -> tuple[McpAccessToken, str]:
    """Create a token. Returns (db row, plaintext token). Plaintext shown once."""
    plaintext = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
    row = McpAccessToken(
        token_hash=_hash(plaintext), name=name, user_id=user_id,
        scopes_json=scopes, expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, plaintext


def verify_token(db: Session, plaintext: str) -> Optional[McpAccessToken]:
    """Return the token row if valid + active, else None."""
    h = _hash(plaintext)
    row = db.query(McpAccessToken).filter(McpAccessToken.token_hash == h).first()
    if not row:
        return None
    if row.revoked_at:
        return None
    if row.expires_at and row.expires_at < datetime.utcnow():
        return None
    row.last_used_at = datetime.utcnow()
    db.commit()
    return row


def is_tool_allowed(scopes: dict, tool_name: str) -> bool:
    """Check whether tool_name matches any allowlist pattern in scopes['tools']."""
    patterns = scopes.get("tools", []) or []
    if not patterns or "*" in patterns:
        return True
    for p in patterns:
        if p == tool_name:
            return True
        if p.endswith("*") and tool_name.startswith(p[:-1]):
            return True
    return False


def is_project_allowed(scopes: dict, project_id: str) -> bool:
    projects = scopes.get("projects", []) or []
    if not projects:
        return True   # no restriction
    return project_id in projects
