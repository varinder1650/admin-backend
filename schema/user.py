from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class TokenData(BaseModel):
    user_id: str

class User(BaseModel):
    name : str = Field(...,min_length=1,max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, min_length=10, max_length=15)  # Made optional
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    role: str = Field(default="user")
    is_active: bool = True

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)  # Made optional
    role: str = Field(default="user")

class UserResponse(User):
    id: str
    provider: str

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    requires_phone: bool
    token_type: str = "bearer"
    user: Optional[UserResponse] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleLogin(BaseModel):
    googleToken: str
    user: dict  # This should contain: email, name, googleId, photo (optional)

class GoogleLoginResponse(BaseModel):
    email: EmailStr
    googleId: str
    name: str
    photo: Optional[str] = None

class UserinDB(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    is_active: bool

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None

class GoogleTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[GoogleLoginResponse] = None