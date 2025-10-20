from fastapi import WebSocket
from datetime import datetime, timezone, timedelta
from bson.objectid import ObjectId
from typing import Optional, List, Dict
import logging
import pytz

logger = logging.getLogger(__name__)

# ✅ Indian Standard Time timezone
IST = pytz.timezone('Asia/Kolkata')

def get_ist_time():
    """Get current time in IST - returns timezone-aware datetime"""
    return datetime.now(IST)

def get_utc_time():
    """Get current time in UTC for MongoDB storage"""
    return datetime.utcnow()

def utc_to_ist_string(utc_dt):
    """Convert UTC datetime to IST string for display"""
    if utc_dt is None:
        return None
    
    if isinstance(utc_dt, datetime):
        # If naive datetime, assume it's UTC
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        
        # Convert to IST
        ist_dt = utc_dt.astimezone(IST)
        return ist_dt.isoformat()
    
    return str(utc_dt)

async def get_all_notifications(websocket: WebSocket, filters: dict, db):
    """Get all admin-created notifications with filters"""
    try:
        # Base query - only show admin-created notifications
        query = {"created_by_admin": True}
        
        # Apply filters
        if filters.get("type"):
            query["type"] = filters["type"]
        
        if filters.get("for"):
            query["for"] = filters["for"]
        
        # Date range filter
        if filters.get("start_date"):
            query["created_at"] = query.get("created_at", {})
            query["created_at"]["$gte"] = datetime.fromisoformat(filters["start_date"])
        
        if filters.get("end_date"):
            query["created_at"] = query.get("created_at", {})
            query["created_at"]["$lte"] = datetime.fromisoformat(filters["end_date"])
        
        # Get notifications with pagination
        skip = filters.get("skip", 0)
        limit = filters.get("limit", 50)
        
        notifications = await db.find_many(
            "notifications",
            query,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit
        )
        
        # Get total count
        total_count = await db.count_documents("notifications", query)
        
        # Build notification list
        notification_list = []
        for notif in notifications:
            # ✅ Use the stored IST string directly
            created_at_ist = notif.get("created_at_ist")
            
            # Fallback: if created_at_ist doesn't exist, convert from UTC
            if not created_at_ist:
                created_at_ist = utc_to_ist_string(notif.get("created_at"))
            
            notif_data = {
                "id": str(notif["_id"]),
                "title": notif["title"],
                "message": notif["message"],
                "type": notif["type"],
                "for": notif.get("for", "specific_user"),
                "created_at": created_at_ist,  # ✅ IST string
                "created_by": notif.get("created_by", "Unknown"),
                "order_id": notif.get("order_id")
            }
            
            # If it's for a specific user, get user details
            if notif.get("for") == "specific_user":
                user_id = notif.get("user_id")
                if user_id:
                    try:
                        user = await db.find_one("users", {"id": user_id})
                        if user:
                            notif_data["user_name"] = user.get("name", "Unknown")
                            notif_data["user_email"] = user.get("email", "N/A")
                            notif_data["user_id"] = user_id
                        else:
                            notif_data["user_name"] = "User Deleted"
                            notif_data["user_email"] = "N/A"
                            notif_data["user_id"] = user_id
                    except:
                        notif_data["user_name"] = "Invalid User"
                        notif_data["user_email"] = "N/A"
                        notif_data["user_id"] = user_id
            else:
                # For broadcast notifications (for: 'all_users')
                notif_data["user_name"] = "All Users"
                notif_data["user_email"] = "Broadcast"
                notif_data["user_id"] = None
                
                # Get active user count at time of viewing
                user_count = await db.count_documents(
                    "users",
                    {"role": "customer", "is_active": True}
                )
                notif_data["recipient_count"] = user_count
            
            notification_list.append(notif_data)
        
        await websocket.send_json({
            "type": "notifications_data",
            "notifications": notification_list,
            "total": total_count,
            "skip": skip,
            "limit": limit
        })
        
        logger.info(f"Sent {len(notification_list)} admin notifications")
        
    except Exception as e:
        logger.error(f"Error getting notifications: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to fetch notifications: {str(e)}"
        })


async def send_notification_to_user(websocket: WebSocket, data: dict, admin_info: dict, db):
    """Send notification to a specific user"""
    try:
        user_id = data.get("user_id")
        title = data.get("title")
        message = data.get("message")
        notification_type = data.get("type", "system")
        order_id = data.get("order_id")
        
        if not all([user_id, title, message]):
            await websocket.send_json({
                "type": "error",
                "message": "User ID, title, and message are required"
            })
            return
        
        # Verify user exists
        user = await db.find_one("users", {"_id": ObjectId(user_id)})
        if not user:
            await websocket.send_json({
                "type": "error",
                "message": "User not found"
            })
            return
        
        # ✅ Get current times
        current_time_utc = get_utc_time()  # For MongoDB (will be stored as UTC)
        current_time_ist = get_ist_time()  # For display
        
        logger.info(f"🕐 Creating notification at IST: {current_time_ist}")
        logger.info(f"🕐 Storing in MongoDB as UTC: {current_time_utc}")
        
        # Create notification
        notification_data = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type,
            "order_id": order_id,
            "read": False,
            "read_at": None,
            "created_at": current_time_utc,  # ✅ Store UTC for MongoDB
            "created_at_ist": current_time_ist.strftime("%Y-%m-%d %H:%M:%S"),  # ✅ Store IST as string
            "timezone": "Asia/Kolkata",  # ✅ Store timezone info
            "created_by": admin_info.get("email"),
            "created_by_admin": True,
            "for": "specific_user"
        }
        
        result = await db.insert_one("notifications", notification_data)
        
        # Verify what was stored
        # stored_notif = await db.find_one("notifications", {"_id": result.inserted_id})
        # logger.info(f"✅ Stored UTC datetime: {stored_notif.get('created_at')}")
        # logger.info(f"✅ Stored IST string: {stored_notif.get('created_at_ist')}")
        
        await websocket.send_json({
            "type": "notification_sent",
            "message": f"Notification sent to {user.get('name', 'user')}",
            # "notification_id": str(result.inserted_id)
        })
        
        logger.info(f"Admin {admin_info.get('email')} sent notification to user {user_id} at IST: {current_time_ist}")
        
    except Exception as e:
        logger.error(f"Error sending notification to user: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to send notification: {str(e)}"
        })


async def send_notification_to_all_users(websocket: WebSocket, data: dict, admin_info: dict, db):
    """Send a single notification with for='all_users'"""
    try:
        title = data.get("title")
        message = data.get("message")
        notification_type = data.get("type", "system")
        user_filter = data.get("user_filter", {})
        
        if not all([title, message]):
            await websocket.send_json({
                "type": "error",
                "message": "Title and message are required"
            })
            return
        
        # Build user query based on filters to get count
        user_query = {"role": "customer"}
        
        if user_filter.get("active_only", True):
            user_query["is_active"] = True
        
        if user_filter.get("verified_only"):
            user_query["is_verified"] = True
        
        # Get count of matching users
        user_count = await db.count_documents("users", user_query)
        
        if user_count == 0:
            await websocket.send_json({
                "type": "error",
                "message": "No users found matching the criteria"
            })
            return
        
        # ✅ Get current times
        current_time_utc = get_utc_time()  # For MongoDB (will be stored as UTC)
        current_time_ist = get_ist_time()  # For display
        
        logger.info(f"🕐 Creating broadcast notification at IST: {current_time_ist}")
        logger.info(f"🕐 Storing in MongoDB as UTC: {current_time_utc}")
        
        # ✅ Create a SINGLE notification with for='all_users'
        notification_data = {
            "title": title,
            "message": message,
            "type": notification_type,
            "for": "all_users",
            "user_filter": user_filter,
            "target_user_count": user_count,
            "read": False,
            "read_at": None,
            "created_at": current_time_utc,  # ✅ Store UTC for MongoDB
            "created_at_ist": current_time_ist.strftime("%Y-%m-%d %H:%M:%S"),  # ✅ Store IST as string
            "timezone": "Asia/Kolkata",  # ✅ Store timezone info
            "created_by": admin_info.get("email"),
            "created_by_admin": True
        }
        
        result = await db.insert_one("notifications", notification_data)
        
        # Verify what was stored
        # stored_notif = await db.find_one("notifications", {"_id": result.inserted_id})
        # logger.info(f"✅ Stored UTC datetime: {stored_notif.get('created_at')}")
        # logger.info(f"✅ Stored IST string: {stored_notif.get('created_at_ist')}")
        
        await websocket.send_json({
            "type": "notification_broadcast_sent",
            "message": f"Notification will be shown to {user_count} users",
            "user_count": user_count,
            # "notification_id": str(result.inserted_id)
        })
        
        logger.info(f"Admin {admin_info.get('email')} created broadcast notification for {user_count} users at IST: {current_time_ist}")
        
    except Exception as e:
        logger.error(f"Error sending broadcast notification: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to send broadcast notification: {str(e)}"
        })


async def delete_notification(websocket: WebSocket, data: dict, admin_info: dict, db):
    """Delete a notification"""
    try:
        notification_id = data.get("notification_id")
        
        if not notification_id:
            await websocket.send_json({
                "type": "error",
                "message": "Notification ID is required"
            })
            return
        
        # Get the notification first
        notification = await db.find_one(
            "notifications",
            {"_id": ObjectId(notification_id), "created_by_admin": True}
        )
        
        if not notification:
            await websocket.send_json({
                "type": "error",
                "message": "Notification not found or not authorized"
            })
            return
        
        # Delete the notification
        result = await db.delete_one(
            "notifications",
            {"_id": ObjectId(notification_id)}
        )
        
        if result:
            await websocket.send_json({
                "type": "notification_deleted",
                "message": "Notification deleted successfully",
                "notification_id": notification_id
            })
            logger.info(f"Admin {admin_info.get('email')} deleted notification: {notification_id}")
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Failed to delete notification"
            })
        
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to delete notification: {str(e)}"
        })


async def get_notification_stats(websocket: WebSocket, db):
    """Get notification statistics for admin-created notifications only"""
    try:
        # Only count admin-created notifications
        base_query = {"created_by_admin": True}
        
        total_notifications = await db.count_documents("notifications", base_query)
        
        # Get broadcast notifications (for='all_users')
        broadcast_count = await db.count_documents(
            "notifications",
            {**base_query, "for": "all_users"}
        )
        
        # Get single user notifications (for='specific_user')
        single_user_count = await db.count_documents(
            "notifications",
            {**base_query, "for": "specific_user"}
        )
        
        # Get notifications by type
        type_stats = await db.aggregate("notifications", [
            {"$match": base_query},
            {
                "$group": {
                    "_id": "$type",
                    "count": {"$sum": 1}
                }
            }
        ])
        
        type_breakdown = {stat["_id"]: stat["count"] for stat in type_stats}
        
        # Get read/unread stats (only for specific user notifications)
        unread_notifications = await db.count_documents(
            "notifications",
            {**base_query, "for": "specific_user", "read": False}
        )
        read_notifications = await db.count_documents(
            "notifications",
            {**base_query, "for": "specific_user", "read": True}
        )
        
        await websocket.send_json({
            "type": "notification_stats",
            "stats": {
                "total": total_notifications,
                "broadcast": broadcast_count,
                "single_user": single_user_count,
                "unread": unread_notifications,
                "read": read_notifications,
                "by_type": type_breakdown
            }
        })
        
        logger.info("Sent admin notification statistics")
        
    except Exception as e:
        logger.error(f"Error getting notification stats: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to fetch notification stats: {str(e)}"
        })