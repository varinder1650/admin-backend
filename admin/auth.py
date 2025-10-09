from datetime import datetime, timedelta
from db.db_manager import get_database
import jwt
from passlib.context import CryptContext
import os
from jwt import ExpiredSignatureError, InvalidTokenError
from dotenv import load_dotenv

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

async def authenticate_admin(credentials: dict):
    """Authenticate admin user"""
    db = get_database()
    print("inside auth function")
    email = credentials.get("email")
    password = credentials.get("password")
    print(email,password)
    if not email or not password:
        return None
    
    # Get user from database
    user = await db.find_one("users", {"email": email})
    print(user)    
    if not user:
        return None
    
    # Verify password
    if not verify_password(password, user.get("hashed_password", "")):
        return None
    
    # Check if user is admin
    if user.get("role") != "admin":
        return None
    
    # Create token
    token = create_access_token(
        data={"sub": email, "role": user["role"]},
        exp_time=timedelta(hours=24)
    )
    
    # Return user info
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user["role"],
        "token": token
    }


async def verify_admin_token(token: str):
    """Verify admin token for reconnection"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
        
        if not email or role != "admin":
            return None
        
        db = get_database()
        user = await db.find_one("users", {"email": email})
        
        if not user or user.get("role") != "admin":
            return None
        
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user["role"],
            "token": token
        }
        
    # except jwt.PyJWTError:
    #     return None
        
    except ExpiredSignatureError:
        return {"error": "token_expired"}
    except InvalidTokenError:
        return {"error": "invalid_token"}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, exp_time: timedelta):
    """Create JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + exp_time
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)