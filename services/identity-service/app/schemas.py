from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    employee_id: Optional[str] = None


class MeResponse(BaseModel):
    user_id: str
    username: str
    role: str
    employee_id: Optional[str] = None
