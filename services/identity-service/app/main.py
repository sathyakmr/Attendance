from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db

app = FastAPI(
    title="Identity Service",
    description="Authentication and role lookup for the Attendance Management System.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=payload.username, is_active=True).first()
    if not user or not security.verify_password(payload.password, user.password_hash):
        # Deliberately identical error for "no such user" and "wrong password"
        # so the endpoint doesn't leak which usernames exist.
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = security.create_access_token(
        user_id=str(user.id),
        role=user.role.value,
        employee_id=str(user.employee_id) if user.employee_id else None,
    )
    return schemas.TokenResponse(
        access_token=token,
        role=user.role.value,
        employee_id=str(user.employee_id) if user.employee_id else None,
    )


def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return security.decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.get("/auth/me", response_model=schemas.MeResponse)
def me(claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(id=claims["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return schemas.MeResponse(
        user_id=str(user.id),
        username=user.username,
        role=user.role.value,
        employee_id=str(user.employee_id) if user.employee_id else None,
    )
