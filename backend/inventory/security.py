import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480"))


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, stored_password_hash: str) -> bool:
    if not stored_password_hash:
        return False

    # Soporte temporal para usuarios antiguos con password en texto plano.
    if not stored_password_hash.startswith("$2"):
        return secrets.compare_digest(plain_password, stored_password_hash)

    return pwd_context.verify(plain_password, stored_password_hash)


def needs_rehash(stored_password_hash: str) -> bool:
    if not stored_password_hash:
        return True

    if not stored_password_hash.startswith("$2"):
        return True

    return pwd_context.needs_update(stored_password_hash)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": subject,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
