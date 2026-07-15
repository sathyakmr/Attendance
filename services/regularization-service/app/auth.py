"""
Verifies JWTs issued by identity-service (shared secret) and exposes
role-based dependency guards. This is intentionally duplicated rather than
imported as a shared package for now — see README "Known shortcuts" for the
plan to extract a common auth library once a third service needs it.
"""
from fastapi import Header, HTTPException, Depends
import jwt

from app.config import settings


def get_current_claims(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*allowed_roles: str):
    def _check(claims: dict = Depends(get_current_claims)) -> dict:
        if claims.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Requires role in {allowed_roles}")
        return claims
    return _check
