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


def require_service_key(x_api_key: str = Header(...)) -> str:
    """For trusted internal callers (attendance-service, regularization-service)
    that aren't acting on behalf of a logged-in human — service-to-service auth,
    not user RBAC."""
    if x_api_key != settings.attendance_service_api_key:
        raise HTTPException(status_code=401, detail="Invalid service API key")
    return x_api_key
