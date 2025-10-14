from datetime import timedelta, datetime
from fastapi import WebSocket
import logging
from admin.connection_manager import manager
from dotenv import load_dotenv
from admin.utils.serialize import serialize_document
from bson import ObjectId
from starlette.websockets import WebSocketDisconnect

load_dotenv()

logger = logging.getLogger(__name__)

async def handle_get_users(websocket: WebSocket, filters: dict, db):
    """Get all users with pagination and filtering"""
    try:
        query = {}
        
        # Apply filters
        if filters.get("role"):
            query["role"] = filters["role"]
        
        if filters.get("search"):
            search_term = filters["search"]
            query["$or"] = [
                {"email": {"$regex": search_term, "$options": "i"}},
                {"name": {"$regex": search_term, "$options": "i"}}
            ]
        
        if filters.get("is_active") is not None:
            query["is_active"] = filters["is_active"]
        
        # Pagination
        page = filters.get("page", 1)
        limit = filters.get("limit", 100)  # Increased limit for admin view
        skip = (page - 1) * limit
        
        # Get total count
        total = await db.count_documents("users", query)
        
        # Get users
        users = await db.find_many(
            "users",
            query,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit
        )
        
        # Remove sensitive data and serialize
        processed_users = []
        for user in users:
            # Remove sensitive fields
            user.pop("hashed_password", None)
            user.pop("password", None)
            
            # Ensure required fields exist
            user.setdefault("name", user.get("email", "Unknown"))
            user.setdefault("status", "active" if user.get("is_active", True) else "inactive")
            user.setdefault("role", "customer")
            user.setdefault("joinedAt", user.get("created_at"))
            
            # Serialize the user
            serialized_user = serialize_document(user)
            processed_users.append(serialized_user)
        
        try:
            await websocket.send_json({
                "type": "users_data",
                "users": processed_users,
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit
            })
        except (WebSocketDisconnect, RuntimeError):
            logger.warning("Tried to send data but the connection is lost")
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Failed to fetch users"
            })
        except (WebSocketDisconnect,RuntimeError):
            logger.warning("connection already disconnected")

async def handle_update_user_role(websocket: WebSocket, data: dict, user_info: dict, db):
    """Update user role"""
    try:
        # ✅ SAFE EMAIL EXTRACTION
        if not user_info or not isinstance(user_info, dict):
            user_email = "system"
        else:
            user_email = (
                user_info.get("email") or 
                user_info.get("sub") or 
                user_info.get("username") or 
                "unknown_user"
            )
        
        user_id = data.get("user_id")
        new_role = data.get("role")
        
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "message": "User ID is required"
            })
            return
        
        if not new_role:
            await websocket.send_json({
                "type": "error",
                "message": "Role is required"
            })
            return
        
        # Validate role
        valid_roles = ["admin", "customer", "delivery_partner", "vendor"]
        if new_role not in valid_roles:
            await websocket.send_json({
                "type": "error",
                "message": f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            })
            return
        
        # Update user role
        updates = {
            "role": new_role,
            "updated_at": datetime.utcnow(),
            "updated_by": user_email
        }
        
        result = await db.update_one(
            "users",
            {"_id": ObjectId(user_id)},
            {"$set": updates}
        )
        
        if result:
            # Get updated user
            updated_user = await db.find_one("users", {"_id": ObjectId(user_id)})
            if updated_user:
                updated_user.pop("hashed_password", None)
                updated_user.setdefault("status", "active" if updated_user.get("is_active", True) else "inactive")
                updated_user = serialize_document(updated_user)
                
                await websocket.send_json({
                    "type": "user_updated",
                    "user": updated_user
                })
                
                # Broadcast to all admins
                await broadcast_users_data(db)
                
                logger.info(f"User role updated: {updated_user['email']} -> {new_role} by {user_email}")
            
            # If role changed to delivery_partner, create delivery profile
            if new_role == "delivery_partner":
                await create_delivery_partner_profile(user_id, db)
                
        else:
            await websocket.send_json({
                "type": "error",
                "message": "User not found"
            })
            
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to update user role: {str(e)}"
        })

async def handle_update_user_status(websocket: WebSocket, data: dict, user_info: dict, db):
    """Update user status (active/inactive)"""
    try:
        # ✅ SAFE EMAIL EXTRACTION
        if not user_info or not isinstance(user_info, dict):
            user_email = "system"
        else:
            user_email = (
                user_info.get("email") or 
                user_info.get("sub") or 
                user_info.get("username") or 
                "unknown_user"
            )
        
        user_id = data.get("user_id")
        new_status = data.get("status")
        
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "message": "User ID is required"
            })
            return
        
        if not new_status:
            await websocket.send_json({
                "type": "error",
                "message": "Status is required"
            })
            return
        
        # Convert status to is_active boolean
        is_active = new_status == "active"
        
        # Update user status
        updates = {
            "is_active": is_active,
            "status": new_status,
            "updated_at": datetime.utcnow(),
            "status_changed_by": user_email
        }
        
        result = await db.update_one(
            "users",
            {"_id": ObjectId(user_id)},
            {"$set": updates}
        )
        
        if result:
            # Get updated user
            updated_user = await db.find_one("users", {"_id": ObjectId(user_id)})
            if updated_user:
                updated_user.pop("hashed_password", None)
                updated_user.setdefault("status", new_status)
                updated_user = serialize_document(updated_user)
                
                await websocket.send_json({
                    "type": "user_status_updated",
                    "user": updated_user
                })
                
                # Broadcast to all admins
                await broadcast_users_data(db)
                
                logger.info(f"User status updated: {updated_user['email']} -> {new_status} by {user_email}")
        else:
            await websocket.send_json({
                "type": "error",
                "message": "User not found"
            })
        
    except Exception as e:
        logger.error(f"Error updating user status: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to update user status: {str(e)}"
        })

async def create_delivery_partner_profile(user_id: str, db):
    """Create delivery partner profile when role is changed"""
    try:
        # Check if profile already exists
        existing = await db.find_one("delivery_partners", {"user_id": ObjectId(user_id)})
        
        if not existing:
            profile = {
                "user_id": ObjectId(user_id),
                "vehicle_type": None,
                "vehicle_number": None,
                "license_number": None,
                "is_available": False,
                "current_location": None,
                "assigned_orders": [],
                "completed_deliveries": 0,
                "rating": 0.0,
                "created_at": datetime.utcnow()
            }
            
            await db.insert_one("delivery_partners", profile)
            logger.info(f"Created delivery partner profile for user: {user_id}")
            
    except Exception as e:
        logger.error(f"Error creating delivery partner profile: {e}")

async def broadcast_users_data(db):
    """Broadcast fresh users data to all connected admins"""
    try:
        users = await db.find_many("users", {}, sort=[("created_at", -1)])
        
        # Process users
        processed_users = []
        for user in users:
            user.pop("hashed_password", None)
            user.pop("password", None)
            user.setdefault("name", user.get("email", "Unknown"))
            user.setdefault("status", "active" if user.get("is_active", True) else "inactive")
            user.setdefault("role", "customer")
            user.setdefault("joinedAt", user.get("created_at"))
            processed_users.append(serialize_document(user))

        message = {
            "type": "users_data",
            "users": processed_users,
            "total": len(processed_users),
            "page": 1,
            "pages": 1
        }
        
        # Send to all connections
        await manager.broadcast_to_all(message)
        
    except Exception as e:
        logger.error(f"Error broadcasting users data: {e}")