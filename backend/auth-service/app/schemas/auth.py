from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class LoginRequest(BaseModel):
    email: str
    password: str
    provider: str
    token: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    email_verified: bool
    provider: Optional[str]
    providers: list[str]
    has_password: bool

class GoogleLoginRequest(BaseModel):
    id_token: str

class VerifyEmailRequest(BaseModel):
    token: str

class SendVerificationRequest(BaseModel):
    email: str

class ForgotPasswordRequest(BaseModel):
    email: str

class SetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8)
    token: str

    @validator('password')
    def validate_password_strength(cls, v):
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v

class TestEmailRequest(BaseModel):
    email: str
    username: str