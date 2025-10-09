from fastapi import HTTPException, status
from app.utils.auth import create_pasword_hash, get_user, verify_password, create_access_token, create_refresh_token
from db.db_manager import DatabaseManager
from schema.user import UserCreate
from bson import ObjectId
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, db: DatabaseManager):
        self.db = db
    async def create_user(self, user_data: UserCreate):
        try:
            logger.info(f"Creating user with email: {user_data.email}")
            
            # Check if email already exists
            existing_email = await self.db.find_one('users', {"email": user_data.email})
            logger.info(f"Existing email check result: {existing_email}")
            
            if existing_email:
                logger.warning(f"Email {user_data.email} already exists")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            
            # Hash password
            logger.info("Hashing password...")
            hashed_password = create_pasword_hash(user_data.password)
            logger.info("Password hashed successfully")
            
            # CRITICAL FIX: Build user document manually to exclude null phone
            # This prevents the MongoDB unique index conflict
            user_doc = {
                "name": user_data.name,
                "email": user_data.email,
                "hashed_password": hashed_password,
                "provider": "local",
                "created_at": datetime.utcnow(),
                "is_active": True,
                "role": getattr(user_data, 'role', 'user')
            }
            
            # Only add phone if it's actually provided and not empty
            requires_phone = True
            if hasattr(user_data, 'phone') and user_data.phone and user_data.phone.strip():
                # Check if phone already exists
                existing_phone = await self.db.find_one("users", {"phone": user_data.phone.strip()})
                logger.info(f"Existing phone check result: {existing_phone}")
                
                if existing_phone:
                    logger.warning(f"Phone {user_data.phone} already exists")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Phone number already exists"
                    )
                user_doc["phone"] = user_data.phone.strip()
                requires_phone = False
            
            # Add other optional fields if they exist and are not empty
            optional_fields = ['address', 'city', 'state', 'pincode']
            for field in optional_fields:
                if hasattr(user_data, field):
                    value = getattr(user_data, field)
                    if value and str(value).strip():
                        user_doc[field] = str(value).strip()
            
            logger.info(f"Final user document keys: {list(user_doc.keys())}")
            logger.info(f"Phone field included: {'phone' in user_doc}")
            logger.info("Inserting user into database...")
            
            user_id = await self.db.insert_one("users", user_doc)
            user_id = str(user_id)
            logger.info(f"User created with ID: {user_id}")
            
            # Get the created user for response
            created_user = await self.db.find_one("users", {"_id": ObjectId(user_id)})
            if not created_user:
                logger.error("Failed to retrieve created user")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )
            
            # Create tokens
            logger.info("Creating access token...")
            access = create_access_token(
                data={'sub': user_id, 'role': created_user.get('role', 'user')},
                exp_time=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30)))
            )
            
            logger.info("Creating refresh token...")
            refresh = await create_refresh_token(user_id, self.db)
            
            logger.info("User registration completed successfully")
            
            # Format user response
            user_response = {
                "id": str(created_user["_id"]),
                "name": created_user["name"],
                "email": created_user["email"],
                "phone": created_user.get("phone"),  # Will be None if not set
                "address": created_user.get("address"),
                "city": created_user.get("city"),
                "state": created_user.get("state"),
                "pincode": created_user.get("pincode"),
                "role": created_user.get("role", "user"),
                "is_active": created_user.get("is_active", True),
                "provider": created_user["provider"]
            }
            
            # Return in TokenOut format
            return {
                "access_token": access,
                "refresh_token": refresh,
                "requires_phone": requires_phone,
                "token_type": "bearer",
                "user": user_response
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user: {str(e)}"
            )

    async def authenticate_user(self, db, username, password):
        try:
            logger.info(f"Authenticating user: {username}")
            auth = await get_user(db, username)
            
            if not auth:
                logger.warning(f"User {username} not found")
                return None
                
            if not verify_password(password, auth['hashed_password']):
                logger.warning(f"Invalid password for user {username}")
                return None
                
            logger.info(f"User {username} authenticated successfully")
            return auth
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None
    
    async def update_user_phone(self, user_id: str, phone: str):
        """Update user's phone number"""
        try:
            logger.info(f"Updating phone for user {user_id}")
            
            # Check if phone already exists for another user
            existing_phone = await self.db.find_one("users", {
                "phone": phone,
                "_id": {"$ne": ObjectId(user_id)}
            })
            
            if existing_phone:
                logger.warning(f"Phone {phone} already exists for another user")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number already exists"
                )
            
            # Update user's phone
            await self.db.update_one(
                "users",
                {"_id": ObjectId(user_id)},
                {"$set": {"phone": phone, "phone_verified": False}}
            )
            
            # Get updated user
            updated_user = await self.db.find_one("users", {"_id": ObjectId(user_id)})
            logger.info(f"Phone updated successfully for user {user_id}")
            return updated_user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Phone update error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update phone number"
            )
    
    # async def create_or_get_google_user(self, email: str, name: str, google_id: str):
    #     """Create or get Google user"""
    #     try:
    #         logger.info(f"Processing Google user: {email}")
            
    #         # Check if user exists
    #         existing_user = await self.db.find_one("users", {"email": email})
            
    #         if existing_user:
    #             logger.info(f"Google user {email} already exists")
    #             return existing_user, existing_user.get("phone") is None
            
    #         # Create new Google user
    #         user_doc = {
    #             "name": name,
    #             "email": email,
    #             "phone": None,
    #             "provider": "google",
    #             "google_id": google_id,
    #             "role": "user",
    #             "is_active": True,
    #             "created_at": datetime.utcnow()
    #         }
            
    #         user_id = await self.db.insert_one("users", user_doc)
    #         created_user = await self.db.find_one("users", {"_id": ObjectId(user_id)})
            
    #         logger.info(f"New Google user {email} created successfully")
    #         return created_user, True  # True indicates requires_phone
            
    #     except Exception as e:
    #         logger.error(f"Google user creation error: {str(e)}")
    #         raise HTTPException(
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             detail="Failed to process Google user"
    #         )
    
    async def create_or_get_google_user(self, email: str, name: str, google_id: str):
        """Create or get Google user with emergency phone workaround"""
        try:
            logger.info(f"Processing Google user: {email}")
            
            # Check if user exists
            existing_user = await self.db.find_one("users", {"email": email})
            
            if existing_user:
                logger.info(f"Google user {email} already exists")
                # Check if user has temporary phone
                requires_phone = (
                    existing_user.get("phone_is_temporary", False) or
                    existing_user.get("requires_phone_update", False) or
                    not existing_user.get("phone") or
                    existing_user.get("phone", "").startswith("TEMP_")
                )
                return existing_user, requires_phone
            
            # Create new Google user with unique temp phone
            import uuid
            import time
            
            timestamp = str(int(time.time()))
            unique_id = str(uuid.uuid4()).replace('-', '')[:8]
            temp_phone = f"TEMP_GOOGLE_{timestamp}_{unique_id}"
            
            user_doc = {
                "name": name,
                "email": email,
                "phone": temp_phone,  # Unique temp phone to avoid conflicts
                "phone_is_temporary": True,
                "phone_verified": False,
                "requires_phone_update": True,
                "provider": "google",
                "google_id": google_id,
                "role": "user",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
            
            user_id = await self.db.insert_one("users", user_doc)
            created_user = await self.db.find_one("users", {"_id": ObjectId(user_id)})
            
            logger.info(f"New Google user {email} created successfully with temp phone")
            return created_user, True  # True indicates requires_phone
            
        except Exception as e:
            logger.error(f"Google user creation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process Google user"
            )

    async def generate_password_reset_token(self, email: str):
        """Generate password reset token for user"""
        try:
            # Check if user exists
            user = await self.db.find_one("users", {"email": email.lower().strip()})
            
            if not user:
                # Return success even if user doesn't exist (security best practice)
                return {
                    "success": True,
                    "message": "If an account exists, you will receive a reset link"
                }
            
            # Generate secure token
            import secrets
            reset_token = secrets.token_urlsafe(32)
            reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            
            # Store reset token
            reset_doc = {
                "user_id": str(user["_id"]),
                "email": email.lower().strip(),
                "token": reset_token,
                "expires_at": reset_token_expiry,
                "used": False,
                "created_at": datetime.utcnow()
            }
            
            # Remove any existing unused tokens for this user
            await self.db.delete_many("password_reset_tokens", {
                "user_id": str(user["_id"]),
                "used": False
            })
            
            # Insert new token
            await self.db.insert_one("password_reset_tokens", reset_doc)
            
            logger.info(f"Password reset token generated for {email}")
            
            return {
                "success": True,
                "token": reset_token,
                "user_name": user["name"],
                "message": "Reset token generated successfully"
            }
            
        except Exception as e:
            logger.error(f"Password reset token generation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate reset token"
            )

    async def reset_user_password(self, token: str, new_password: str):
        """Reset user password using token"""
        try:
            # Find valid reset token
            reset_token_doc = await self.db.find_one("password_reset_tokens", {
                "token": token,
                "used": False,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if not reset_token_doc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset token"
                )
            
            # Hash new password
            from app.utils.auth import create_pasword_hash
            hashed_password = create_pasword_hash(new_password)
            
            # Update user password
            user_id = reset_token_doc["user_id"]
            await self.db.update_one(
                "users",
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "hashed_password": hashed_password,
                    "password_updated_at": datetime.utcnow()
                }}
            )
            
            # Mark token as used
            await self.db.update_one(
                "password_reset_tokens",
                {"_id": reset_token_doc["_id"]},
                {"$set": {
                    "used": True,
                    "used_at": datetime.utcnow()
                }}
            )
            
            logger.info(f"Password reset successful for user {user_id}")
            
            return {
                "success": True,
                "message": "Password reset successfully"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )