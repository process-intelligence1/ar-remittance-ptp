"""Admin key for /api/admin/* (until the demo login in M08).

Callers send header  X-Admin-Key: <key>.  The key comes from ADMIN_API_KEY (Azure: Key Vault
secret "admin-api-key"). No key configured = admin endpoints switched off (403).
"""
import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False,
                                description="Admin key (Key Vault secret admin-api-key)")


def require_admin_key(key: str | None = Security(admin_key_header)) -> None:
    expected = get_settings().admin_api_key
    if not expected:
        raise HTTPException(403, "Admin endpoints are switched off here (no ADMIN_API_KEY configured).")
    if not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "Missing or wrong X-Admin-Key header.", headers={"WWW-Authenticate": "X-Admin-Key"})
