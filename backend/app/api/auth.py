"""Demo login (the final login of this app): pick one of the four demo users, type the demo access code, get a token.

- POST /api/auth/demo-login   {"user": "<e-mail>", "access_code": "..."} -> {"token", "expires_at", "user"}
- GET  /api/auth/demo-users   the four demo users (names and roles, public demo data) for the picker
- GET  /api/auth/me           who the token belongs to

The access code (DEMO_ACCESS_CODE) and the signing key (JWT_SECRET) come from Key Vault in Azure; empty = login off.
Tokens last TOKEN_HOURS (default 10); an expired or bad token gets 401. Login is rate limited per IP (10 attempts per
minute, then a short lockout). Successful, failed and blocked logins are written to ar.audit_log - never the code.
Signed download links for attachments (short-lived, tied to the attachment id) use the same key.
"""
import hmac
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.gmail.poller import current_business_date
from app.models.ar import AppUser, AuditLog

router = APIRouter(prefix="/api/auth", tags=["Login"])
bearer = HTTPBearer(auto_error=False, description="Token from POST /api/auth/demo-login")
ALGORITHM = "HS256"


@dataclass(frozen=True)
class CurrentUser:
    email: str
    name: str
    role: str


# --------------------------------------------------------------------------- rate limit
class LoginLimiter:
    """Per IP: at most `max_attempts` login attempts in `window_s`; beyond that the IP is locked out for `lockout_s`."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._attempts: dict[str, deque] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}

    def retry_after(self, ip: str) -> int:
        """Seconds the IP must still wait (0 = free to try)."""
        left = self._locked_until.get(ip, 0) - self._clock()
        if left > 0:
            return int(left) + 1
        self._locked_until.pop(ip, None)
        return 0

    def attempt(self, ip: str) -> tuple[int, bool]:
        """Count one attempt. Returns (seconds to wait, newly locked). (0, False) = allowed; the attempt that trips the
        limit is refused."""
        s, now = get_settings(), self._clock()
        if (wait := self.retry_after(ip)):
            return wait, False
        q = self._attempts[ip]
        while q and now - q[0] > s.login_window_s:
            q.popleft()
        if len(q) >= s.login_max_attempts:
            self._locked_until[ip] = now + s.login_lockout_s
            q.clear()
            return s.login_lockout_s, True
        q.append(now)
        if len(self._attempts) > 5000:  # forget idle IPs
            for k in [k for k, v in self._attempts.items() if not v or now - v[-1] > s.login_window_s]:
                self._attempts.pop(k, None)
        return 0, False

    def reset(self) -> None:
        self._attempts.clear()
        self._locked_until.clear()


limiter = LoginLimiter()


# --------------------------------------------------------------------------- tokens
def _secret() -> str:
    key = get_settings().jwt_secret
    if len(key) < 16:
        raise HTTPException(503, "Login is switched off here (JWT_SECRET is not configured).")
    return key


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_token(user: AppUser) -> tuple[str, datetime]:
    exp = _now() + timedelta(hours=get_settings().token_hours)
    payload = {"typ": "access", "sub": user.email, "name": user.display_name, "role": user.role,
               "iat": _now(), "exp": exp}
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM), exp


def make_file_token(attachment_id: int, user_email: str) -> str:
    s = get_settings()
    return jwt.encode({"typ": "file", "att": attachment_id, "sub": user_email,
                       "exp": _now() + timedelta(seconds=s.file_url_ttl_s)}, _secret(), algorithm=ALGORITHM)


def read_token(token: str, typ: str) -> dict:
    try:
        claims = jwt.decode(token, _secret(), algorithms=[ALGORITHM], options={"require": ["exp", "typ"]})
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired - sign in again.", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token.", headers={"WWW-Authenticate": "Bearer"})
    if claims.get("typ") != typ:
        raise HTTPException(401, "Invalid token.", headers={"WWW-Authenticate": "Bearer"})
    return claims


def current_user(creds: HTTPAuthorizationCredentials | None = Security(bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(401, "Sign in first (Authorization: Bearer <token>).", headers={"WWW-Authenticate": "Bearer"})
    c = read_token(creds.credentials, "access")
    return CurrentUser(c["sub"], c.get("name", c["sub"]), c["role"])


# --------------------------------------------------------------------------- endpoints
class LoginRequest(BaseModel):
    user: str
    access_code: str


def _audit(db: Session, action: str, ip: str, user: str | None, **extra) -> None:
    db.add(AuditLog(business_date=current_business_date(db), actor=user or "anonymous", entity_type="auth",
                    entity_id=None, action=action, details={"ip": ip, **extra}))
    db.commit()


@router.get("/demo-users", summary="The demo users to pick from")
def demo_users(db: Session = Depends(get_db)):
    return [{"email": u.email, "name": u.display_name, "role": u.role}
            for u in db.scalars(select(AppUser).where(AppUser.active.is_(True)).order_by(AppUser.id))]


@router.post("/demo-login", summary="Sign in with a demo user and the demo access code")
def demo_login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    if not s.demo_access_code or len(s.jwt_secret) < 16:
        raise HTTPException(503, "Login is switched off here (no DEMO_ACCESS_CODE / JWT_SECRET configured).")
    ip = request.client.host if request.client else "unknown"
    wait, newly_locked = limiter.attempt(ip)
    if wait:
        if newly_locked:  # audit the lockout once, not every refused request
            _audit(db, "LOGIN_BLOCKED", ip, None, lockout_s=wait)
        raise HTTPException(429, f"Too many login attempts. Try again in {wait} s.", headers={"Retry-After": str(wait)})
    user = db.scalar(select(AppUser).where(AppUser.email == body.user.strip().lower(), AppUser.active.is_(True)))
    code_ok = hmac.compare_digest(body.access_code.encode(), s.demo_access_code.encode())
    if not (user and code_ok):
        _audit(db, "LOGIN_FAILED", ip, body.user.strip()[:120], reason="wrong access code" if user else "unknown user")
        raise HTTPException(401, "Wrong user or access code.")  # the same answer for both
    token, exp = make_token(user)
    _audit(db, "LOGIN_OK", ip, user.email, role=user.role)
    return {"token": token, "token_type": "Bearer", "expires_at": exp,
            "user": {"email": user.email, "name": user.display_name, "role": user.role}}


@router.get("/me", summary="Who am I")
def me(user: CurrentUser = Depends(current_user)):
    return {"email": user.email, "name": user.name, "role": user.role}
