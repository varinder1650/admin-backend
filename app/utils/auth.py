import uuid
from schema.user import User, TokenData, UserResponse, UserinDB
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import date, datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, Depends, status
import os
from dotenv import load_dotenv
from db.db_manager import DatabaseManager, get_database
import asyncio
from fastapi import WebSocket
import json
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)
load_dotenv()

pwd_context = CryptContext(
    schemes=['bcrypt'], 
    deprecated="auto",
    bcrypt__rounds=12
)
Oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="token")

credentials_exception = HTTPException(
    status_code=401,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_user(db: DatabaseManager, username: str):
    """Get user by email"""
    user = await db.find_one('users', {"email": username})
    if not user:
        print("user not registered")
        return None
    return user

async def get_user_by_id(db: DatabaseManager, user_id: str):
    """Get user by ID"""
    if not ObjectId.is_valid(user_id):
        return None
    user = await db.find_one('users', {"_id": ObjectId(user_id)})
    return user

def verify_password(plain_pass: str, hash_pass: str):
    """Verify password against hash"""
    return pwd_context.verify(plain_pass, hash_pass)

def create_pasword_hash(password: str):
    """Create password hash"""
    return pwd_context.hash(password)

def create_access_token(data: dict, exp_time: timedelta):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (exp_time if exp_time else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM'))
    return token

async def create_refresh_token(user_id: str, db: DatabaseManager):
    jti = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(days = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS')))
    token_data = {"sub": user_id, "jti": jti, "exp": expire}
    encoded = jwt.encode(token_data, os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM'))
    await db.insert_one("refresh_tokens", {"user_id": user_id, "jti": jti, "expire": expire})
    return encoded

async def decode_token(token: str, db: DatabaseManager):
    """Decode and validate JWT token - FIXED VERSION"""
    try:
        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
        user_id: str = payload.get("sub")  # ✅ This is the user ID
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # ✅ Get user by ID instead of email
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    return UserinDB(
        id=str(user["_id"]),
        email=user["email"], 
        role=user['role'], 
        name=user.get('name', ''),
        is_active=user.get('is_active', True)
    )

async def current_active_user(
    token: str = Depends(Oauth_2_scheme), 
    db: DatabaseManager = Depends(get_database)
):
    """Get current active user from token"""
    return await decode_token(token, db)

async def get_current_user(current_user: UserinDB = Depends(current_active_user)):
    """Get current user with active status check"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def authenticate_websocket(websocket: WebSocket):
    """Authenticate WebSocket connection"""
    try:
        auth_message = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=5.0
        )

        auth_data = json.loads(auth_message)
        token = auth_data.get("token")

        if not token:
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

        db = get_database()
        user_data = await decode_token(token, db)
        
        if user_data.role != "admin":
            await websocket.send_json({
                "type": "error",
                "message": "Admin access required"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

        user = await db.find_one("users", {"email": user_data.email})

        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

        await websocket.send_json({
            "type": "auth_success",
            "message": "Authentication Successful"
        })

        return {
            "email": user["email"],
            "role": user['role'],
            "name": user.get('name', ''),
            "id": str(user['_id'])
        }

    except asyncio.TimeoutError:
        await websocket.close(code=1008, reason="Authentication timeout")
        return None
    except Exception as e:
        logger.error(f"WebSocket auth error: {str(e)}")
        await websocket.close(code=1008, reason="Authentication failed")
        return None