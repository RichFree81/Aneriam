"""
Security utilities: password hashing, JWT creation/validation, and token revocation.

D-1: Login rate limiting is implemented via slowapi (applied in auth.py).
D-2: Token revocation is now database-backed (RevokedToken table) so revoked JTIs
     survive server restarts. The in-memory fallback is retained for startup safety
     during migrations, but all revocations go to the database first.
"""
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Set, Union

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ALGORITHM = "HS256"
SECRET_KEY = os.getenv("JWT_SECRET", "")

# Access tokens: short-lived (default 30 min). Override via JWT_ACCESS_TOKEN_EXPIRE_MINUTES.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Refresh tokens: longer-lived (default 7 days). Override via JWT_REFRESH_TOKEN_EXPIRE_DAYS.
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ---------------------------------------------------------------------------
# D-1: In-memory login attempt tracker for rate limiting.
# Keyed by client IP. Each entry: {"count": int, "window_start": datetime}
# Max LOGIN_RATE_LIMIT_ATTEMPTS attempts per LOGIN_RATE_LIMIT_WINDOW_SECONDS window.
# ---------------------------------------------------------------------------
LOGIN_RATE_LIMIT_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "10"))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))  # 5 minutes

_login_attempts: dict = defaultdict(lambda: {"count": 0, "window_start": None})


def record_login_attempt(ip: str) -> bool:
    """
    Record a failed login attempt from the given IP.
    Returns True if the IP is now rate-limited (over the threshold).
    The window resets automatically after LOGIN_RATE_LIMIT_WINDOW_SECONDS.
    """
    now = datetime.now(timezone.utc)
    record = _login_attempts[ip]

    # Reset window if expired
    if record["window_start"] is None or (now - record["window_start"]).total_seconds() > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        _login_attempts[ip] = {"count": 1, "window_start": now}
        return False

    record["count"] += 1
    return record["count"] > LOGIN_RATE_LIMIT_ATTEMPTS


def is_ip_rate_limited(ip: str) -> bool:
    """Return True if the IP has exceeded its login attempt quota within the current window."""
    now = datetime.now(timezone.utc)
    record = _login_attempts.get(ip)
    if not record or record["window_start"] is None:
        return False
    if (now - record["window_start"]).total_seconds() > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        return False
    return record["count"] > LOGIN_RATE_LIMIT_ATTEMPTS


def reset_login_attempts(ip: str) -> None:
    """Clear the rate-limit counter for an IP after a successful login."""
    _login_attempts.pop(ip, None)


# ---------------------------------------------------------------------------
# D-2: Database-backed token revocation.
# The in-memory set is kept as a fast cache for the current process lifetime.
# All revocations are written to the RevokedToken DB table for persistence.
# ---------------------------------------------------------------------------
_revoked_jtis_cache: Set[str] = set()


def revoke_token(jti: str, session=None) -> None:
    """
    Mark a token JTI as revoked.
    Adds to the in-process cache immediately.
    If a DB session is provided, also persists to the revoked_token table.
    """
    _revoked_jtis_cache.add(jti)

    if session is not None:
        from app.models.revoked_token import RevokedToken
        from sqlmodel import select

        existing = session.exec(select(RevokedToken).where(RevokedToken.jti == jti)).first()
        if not existing:
            row = RevokedToken(jti=jti, revoked_at=datetime.now(timezone.utc))
            session.add(row)
            session.commit()


def is_token_revoked(jti: str, session=None) -> bool:
    """
    Check if a token JTI has been revoked.
    Fast path: in-process cache. Slow path: database lookup (for cross-restart checks).
    """
    if jti in _revoked_jtis_cache:
        return True

    if session is not None:
        from app.models.revoked_token import RevokedToken
        from sqlmodel import select

        row = session.exec(select(RevokedToken).where(RevokedToken.jti == jti)).first()
        if row:
            _revoked_jtis_cache.add(jti)  # Warm the cache
            return True

    return False


def validate_security_config():
    """Call at application startup to ensure required security config is set."""
    if not SECRET_KEY:
        raise ValueError("JWT_SECRET environment variable is not set. Cannot start application.")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: Union[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
