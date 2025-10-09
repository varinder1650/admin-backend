# from bson import ObjectId
# from fastapi import APIRouter, HTTPException, Depends, status, Request
# import logging
# from dotenv import load_dotenv
# import os
# from datetime import timedelta,datetime
# from app.services.auth_service import AuthService
# from db.db_manager import DatabaseManager,get_database
# from schema.user import UserCreate,TokenOut,UserResponse,UserLogin, GoogleLogin
# from app.utils.auth import create_refresh_token, get_current_user,create_access_token
# # from slowapi import Limiter
# # from slowapi.errors import RateLimitExceeded
# # from slowapi.util import get_remote_address
# # from fastapi.responses import JSONResponse
# from pydantic import BaseModel, EmailStr, Field
# from jose import JWTError, jwt

# load_dotenv()

# logger = logging.getLogger(__name__)
# router = APIRouter()

# # Phone update model
# class PhoneUpdate(BaseModel):
#     phone: str = Field(..., min_length=10, max_length=15)

# # Refresh token model
# class RefreshTokenRequest(BaseModel):
#     refresh_token: str

# @router.post("/register", response_model=TokenOut)
# async def register_user(user_data: UserCreate, db: DatabaseManager = Depends(get_database)):
#     try:
#         auth_service = AuthService(db)
#         result = await auth_service.create_user(user_data)
#         return TokenOut(**result)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"Registration error: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Registration service error"
#         )

# @router.post("/login", response_model=TokenOut)
# async def login_user(user_data: UserLogin, db: DatabaseManager = Depends(get_database)):
#     try:
#         auth_service = AuthService(db)
#         user = await auth_service.authenticate_user(db, user_data.email, user_data.password)
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED, 
#                 detail="Invalid username or password",
#                 headers={"WWW-Authenticate": "Bearer"}
#             )
        
#         access = create_access_token(
#             data={'sub': str(user['_id']), 'role': user['role']},
#             exp_time=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')))
#         )
#         refresh = await create_refresh_token(str(user['_id']), db)
        
#         logger.info(f"User {user['email']} logged in successfully")
        
#         # Format user response
#         user_response = {
#             "id": str(user["_id"]),
#             "name": user["name"],
#             "email": user["email"],
#             "phone": user.get("phone"),
#             "address": user.get("address"),
#             "city": user.get("city"),
#             "state": user.get("state"),
#             "pincode": user.get("pincode"),
#             "role": user.get("role", "user"),
#             "is_active": user.get("is_active", True),
#             "provider": user.get("provider", "local")
#         }
        
#         return TokenOut(
#             access_token=access,
#             refresh_token=refresh,
#             requires_phone=user.get("phone") is None,
#             token_type="bearer",
#             user=UserResponse(**user_response)
#         )
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Login error: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Authentication service error"
#         )

# @router.post("/phone")
# async def update_phone(
#     phone_data: PhoneUpdate, 
#     current_user=Depends(get_current_user),
#     db: DatabaseManager = Depends(get_database)
# ):
#     try:
#         auth_service = AuthService(db)
#         updated_user = await auth_service.update_user_phone(current_user.id, phone_data.phone)
        
#         # Format user response
#         user_response = {
#             "id": str(updated_user["_id"]),
#             "name": updated_user["name"],
#             "email": updated_user["email"],
#             "phone": updated_user.get("phone"),
#             "address": updated_user.get("address"),
#             "city": updated_user.get("city"),
#             "state": updated_user.get("state"),
#             "pincode": updated_user.get("pincode"),
#             "role": updated_user.get("role", "user"),
#             "is_active": updated_user.get("is_active", True),
#             "provider": updated_user.get("provider", "local")
#         }
        
#         return {
#             "success": True,
#             "message": "Phone number updated successfully",
#             "user": user_response
#         }
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"Phone update error: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to update phone number"
#         )

# @router.get("/profile")
# async def get_me(current_user=Depends(get_current_user)):
#     return current_user

# class UpdateUser(BaseModel):
#     name: str

# @router.put("/profile")
# async def update_profile(user_info:UpdateUser,db: DatabaseManager = Depends(get_database),current_user = Depends(get_current_user)):
#     try:
#         result = await db.update_one("users", {"_id": ObjectId(current_user.id)}, {"name":user_info.name})
#         print(result)
#         return {
#             "name": user_info.name,
#         }
#     # except ValidationError as e:
#     #     print(f"Validation error: {e}")
#     #     raise HTTPException(status_code=422, detail=str(e))
#     except Exception as e:
#         print(f"Other error: {e}")
#         raise e

# @router.post("/google", response_model=TokenOut)
# async def google_login(user_info: GoogleLogin, db: DatabaseManager = Depends(get_database)):
#     try:
#         logger.info(f"Google login attempt: {user_info.dict()}")
        
#         # Verify the Google ID token first (optional but recommended)
#         # For now, we'll trust the client-side verification
        
#         # Extract user info from the request
#         user_data = user_info.user
#         email = user_data.get("email")
#         name = user_data.get("name") 
#         google_id = user_data.get("googleId") or user_data.get("id")
        
#         if not email or not name:
#             logger.error(f"Missing required Google user data: email={email}, name={name}")
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Missing required user information from Google"
#             )
        
#         logger.info(f"Processing Google login for: {email}")
        
#         auth_service = AuthService(db)
        
#         # Create or get Google user
#         user, requires_phone = await auth_service.create_or_get_google_user(email, name, google_id)
        
#         # Create JWT tokens for our app (not Google tokens!)
#         access = create_access_token(
#             data={'sub': str(user['_id']), 'role': user.get('role', 'user')},
#             exp_time=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30)))
#         )
#         refresh = await create_refresh_token(str(user['_id']), db)
        
#         # Format user response
#         user_response = {
#             "id": str(user["_id"]),
#             "name": user["name"],
#             "email": user["email"],
#             "phone": user.get("phone"),
#             "address": user.get("address"),
#             "city": user.get("city"),
#             "state": user.get("state"),
#             "pincode": user.get("pincode"),
#             "role": user.get("role", "user"),
#             "is_active": user.get("is_active", True),
#             "provider": user.get("provider", "google")
#         }
        
#         logger.info(f"Google user {email} logged in successfully, requires_phone: {requires_phone}")
        
#         return TokenOut(
#             access_token=access,
#             refresh_token=refresh,
#             requires_phone=requires_phone,
#             token_type="bearer",
#             user=UserResponse(**user_response)
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Google login error: {str(e)}")
#         import traceback
#         logger.error(f"Full traceback: {traceback.format_exc()}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Google authentication failed: {str(e)}"
#         )


# @router.post("/refresh")
# async def refresh_token(
#     refresh_data: dict,
#     db: DatabaseManager = Depends(get_database)
# ):
#     try:
#         refresh_token = refresh_data.get("refresh_token")
#         if not refresh_token:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Refresh token required"
#             )
        
#         # Decode refresh token
#         try:
#             payload = jwt.decode(refresh_token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
#             user_id = payload.get("sub")
#             jti = payload.get("jti")
#         except JWTError:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid refresh token"
#             )
        
#         # Check if refresh token exists in database
#         stored_token = await db.find_one("refresh_tokens", {"user_id": user_id, "jti": jti})
#         if not stored_token:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Refresh token not found"
#             )
        
#         # Check if token is expired
#         if stored_token["expire"] < datetime.utcnow():
#             await db.delete_one("refresh_tokens", {"jti": jti})
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Refresh token expired"
#             )
        
#         # Get user
#         user = await db.find_one("users", {"_id": ObjectId(user_id)})
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="User not found"
#             )
        
#         # Create new access token
#         access_token = create_access_token(
#             data={'sub': user_id, 'role': user['role']},
#             exp_time=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30)))
#         )
        
#         return {
#             "access_token": access_token,
#             "token_type": "bearer"
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Token refresh error: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Token refresh failed"
#         )

# @router.post("/forgot-password")
# async def forgot_password(email):
#     print(email)


from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, status, Request
import logging
from dotenv import load_dotenv
import os
from datetime import timedelta, datetime
from app.services.auth_service import AuthService
from db.db_manager import DatabaseManager, get_database
from schema.user import UserCreate, TokenOut, UserResponse, UserLogin, GoogleLogin
from app.utils.auth import create_refresh_token, get_current_user, create_access_token
from pydantic import BaseModel, EmailStr, Field
from jose import JWTError, jwt
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

# Phone update model
class PhoneUpdate(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)

# Refresh token model
class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Forgot password model
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

# Reset password model
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

@router.post("/register", response_model=TokenOut)
async def register_user(user_data: UserCreate, db: DatabaseManager = Depends(get_database)):
    try:
        auth_service = AuthService(db)
        result = await auth_service.create_user(user_data)
        return TokenOut(**result)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration service error"
        )

@router.post("/login", response_model=TokenOut)
async def login_user(user_data: UserLogin, db: DatabaseManager = Depends(get_database)):
    try:
        auth_service = AuthService(db)
        user = await auth_service.authenticate_user(db, user_data.email, user_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        access = create_access_token(
            data={'sub': str(user['_id']), 'role': user['role']},
            exp_time=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')))
        )
        refresh = await create_refresh_token(str(user['_id']), db)
        
        logger.info(f"User {user['email']} logged in successfully")
        
        # Check if user has a temporary phone
        display_phone = user.get("phone")
        requires_phone = False
        
        if display_phone and (
            display_phone.startswith("TEMP_") or 
            user.get("phone_is_temporary", False) or
            user.get("requires_phone_update", False)
        ):
            display_phone = None
            requires_phone = True
        
        # Format user response
        user_response = {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "phone": display_phone,
            "address": user.get("address"),
            "city": user.get("city"),
            "state": user.get("state"),
            "pincode": user.get("pincode"),
            "role": user.get("role", "user"),
            "is_active": user.get("is_active", True),
            "provider": user.get("provider", "local")
        }
        
        return TokenOut(
            access_token=access,
            refresh_token=refresh,
            requires_phone=requires_phone,
            token_type="bearer",
            user=UserResponse(**user_response)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

@router.post("/phone")
async def update_phone(
    phone_data: PhoneUpdate, 
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    try:
        logger.info(f"Phone update request for user {current_user.id}")
        logger.info(f"Phone data: {phone_data.phone}")
        
        auth_service = AuthService(db)
        updated_user = await auth_service.update_user_phone(current_user.id, phone_data.phone)
        
        # Format user response - show real phone now
        user_response = {
            "id": str(updated_user["_id"]),
            "name": updated_user["name"],
            "email": updated_user["email"],
            "phone": updated_user.get("phone"),  # Now shows real phone
            "address": updated_user.get("address"),
            "city": updated_user.get("city"),
            "state": updated_user.get("state"),
            "pincode": updated_user.get("pincode"),
            "role": updated_user.get("role", "user"),
            "is_active": updated_user.get("is_active", True),
            "provider": updated_user.get("provider", "local")
        }
        
        logger.info(f"Phone update successful for user {current_user.id}")
        
        return {
            "success": True,
            "message": "Phone number updated successfully",
            "user": user_response
        }
    except HTTPException as e:
        logger.error(f"Phone update HTTP error: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Phone update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update phone number"
        )

@router.get("/profile")
async def get_me(current_user=Depends(get_current_user)):
    return current_user

class UpdateUser(BaseModel):
    name: str

@router.put("/profile")
async def update_profile(user_info: UpdateUser, db: DatabaseManager = Depends(get_database), current_user=Depends(get_current_user)):
    try:
        result = await db.update_one("users", {"_id": ObjectId(current_user.id)}, {"$set": {"name": user_info.name}})
        
        # Get updated user
        updated_user = await db.find_one("users", {"_id": ObjectId(current_user.id)})
        
        return {
            "success": True,
            "user": {
                "id": str(updated_user["_id"]),
                "name": updated_user["name"],
                "email": updated_user["email"],
                "phone": updated_user.get("phone"),
                "role": updated_user.get("role", "user"),
            }
        }
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.post("/google", response_model=TokenOut)
async def google_login(user_info: GoogleLogin, db: DatabaseManager = Depends(get_database)):
    try:
        logger.info(f"Google login attempt: {user_info.dict()}")
        
        # Extract user info from the request
        user_data = user_info.user
        email = user_data.get("email")
        name = user_data.get("name") 
        google_id = user_data.get("googleId") or user_data.get("id")
        
        if not email or not name:
            logger.error(f"Missing required Google user data: email={email}, name={name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required user information from Google"
            )
        
        logger.info(f"Processing Google login for: {email}")
        
        auth_service = AuthService(db)
        
        # Create or get Google user
        user, requires_phone = await auth_service.create_or_get_google_user(email, name, google_id)
        
        # Create JWT tokens for our app
        access = create_access_token(
            data={'sub': str(user['_id']), 'role': user.get('role', 'user')},
            exp_time=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30)))
        )
        refresh = await create_refresh_token(str(user['_id']), db)
        
        # Format user response - hide temp phone if applicable
        display_phone = user.get("phone")
        if display_phone and (
            display_phone.startswith("TEMP_") or 
            user.get("phone_is_temporary", False)
        ):
            display_phone = None
            requires_phone = True
        
        user_response = {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "phone": display_phone,
            "address": user.get("address"),
            "city": user.get("city"),
            "state": user.get("state"),
            "pincode": user.get("pincode"),
            "role": user.get("role", "user"),
            "is_active": user.get("is_active", True),
            "provider": user.get("provider", "google")
        }
        
        logger.info(f"Google user {email} logged in successfully, requires_phone: {requires_phone}")
        
        return TokenOut(
            access_token=access,
            refresh_token=refresh,
            requires_phone=requires_phone,
            token_type="bearer",
            user=UserResponse(**user_response)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google login error: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google authentication failed: {str(e)}"
        )

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DatabaseManager = Depends(get_database)
):
    try:
        logger.info(f"Forgot password request for email: {request.email}")
        
        # Check if user exists
        user = await db.find_one("users", {"email": request.email.lower().strip()})
        
        # Always return success to prevent email enumeration attacks
        if not user:
            logger.warning(f"Forgot password request for non-existent email: {request.email}")
            return {
                "success": True,
                "message": "If an account with this email exists, you will receive a password reset link."
            }
        
        # Generate secure reset token
        reset_token = secrets.token_urlsafe(32)
        reset_token_expiry = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        
        # Store reset token in database
        reset_token_doc = {
            "user_id": str(user["_id"]),
            "token": reset_token,
            "expires_at": reset_token_expiry,
            "used": False,
            "created_at": datetime.utcnow()
        }
        
        await db.insert_one("password_reset_tokens", reset_token_doc)
        
        # Send email (implement email service)
        try:
            await send_password_reset_email(request.email, user["name"], reset_token)
        except Exception as email_error:
            logger.error(f"Failed to send reset email: {email_error}")
            # Don't fail the request if email fails, just log it
        
        logger.info(f"Password reset token generated for user {user['_id']}")
        
        return {
            "success": True,
            "message": "If an account with this email exists, you will receive a password reset link."
        }
        
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: DatabaseManager = Depends(get_database)
):
    try:
        logger.info(f"Password reset attempt with token: {request.token[:10]}...")
        
        # Find and validate reset token
        reset_token_doc = await db.find_one("password_reset_tokens", {
            "token": request.token,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if not reset_token_doc:
            logger.warning(f"Invalid or expired reset token: {request.token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Validate new password
        if len(request.new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )
        
        # Hash new password
        from app.utils.auth import create_pasword_hash
        hashed_password = create_pasword_hash(request.new_password)
        
        # Update user password
        user_id = reset_token_doc["user_id"]
        await db.update_one(
            "users",
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_password": hashed_password, "password_updated_at": datetime.utcnow()}}
        )
        
        # Mark token as used
        await db.update_one(
            "password_reset_tokens",
            {"_id": reset_token_doc["_id"]},
            {"$set": {"used": True, "used_at": datetime.utcnow()}}
        )
        
        logger.info(f"Password reset successful for user {user_id}")
        
        return {
            "success": True,
            "message": "Password has been reset successfully. You can now log in with your new password."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.post("/refresh")
async def refresh_token(
    refresh_data: dict,
    db: DatabaseManager = Depends(get_database)
):
    try:
        refresh_token = refresh_data.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token required"
            )
        
        # Decode refresh token
        try:
            payload = jwt.decode(refresh_token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
            user_id = payload.get("sub")
            jti = payload.get("jti")
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Check if refresh token exists in database
        stored_token = await db.find_one("refresh_tokens", {"user_id": user_id, "jti": jti})
        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found"
            )
        
        # Check if token is expired
        if stored_token["expire"] < datetime.utcnow():
            await db.delete_one("refresh_tokens", {"jti": jti})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired"
            )
        
        # Get user
        user = await db.find_one("users", {"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new access token
        access_token = create_access_token(
            data={'sub': user_id, 'role': user['role']},
            exp_time=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30)))
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

# Email service function
async def send_password_reset_email(email: str, name: str, reset_token: str):
    """Send password reset email"""
    try:
        # Email configuration (you'll need to set these in your .env file)
        SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
        SMTP_USER = os.getenv('SMTP_USER')  # Your email
        SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')  # Your app password
        FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
        
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured, skipping email")
            return
        
        # Create reset link (adjust URL to your frontend)
        frontend_url = os.getenv('FRONTEND_URL', 'https://your-app.com')
        reset_link = f"{frontend_url}/auth/reset-password?token={reset_token}"
        
        # Create email content
        subject = "SmartBag - Password Reset Request"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                .container {{ max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; }}
                .header {{ background-color: #007AFF; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .button {{ 
                    display: inline-block; 
                    background-color: #007AFF; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin: 20px 0;
                }}
                .footer {{ color: #666; font-size: 12px; padding: 20px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>SmartBag</h1>
                </div>
                <div class="content">
                    <h2>Password Reset Request</h2>
                    <p>Hello {name},</p>
                    <p>We received a request to reset your password for your SmartBag account.</p>
                    <p>Click the button below to reset your password:</p>
                    <a href="{reset_link}" class="button">Reset Password</a>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #007AFF;">{reset_link}</p>
                    <p><strong>This link will expire in 1 hour.</strong></p>
                    <p>If you didn't request this password reset, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>SmartBag - Your favorite food delivery app</p>
                    <p>This is an automated email. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = email
        
        # Add HTML content
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Password reset email sent to {email}")
        
    except Exception as e:
        logger.error(f"Email sending error: {str(e)}")
        raise