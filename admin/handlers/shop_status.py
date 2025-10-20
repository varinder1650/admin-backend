# admin/handlers/__init__.py - ADD THIS IMPORT
# from admin.handlers.shop_status import get_shop_status, update_shop_status
from fastapi import WebSocket
from datetime import datetime
import logging
from admin.utils.serialize import serialize_document

logger = logging.getLogger(__name__)

async def get_shop_status(websocket: WebSocket, db):
    """Get current shop status"""
    try:
        logger.info("📡 Fetching shop status...")
        
        # Get from database
        status_doc = await db.find_one("shop_status", {})
        
        if not status_doc:
            # Default to open if no status set
            logger.info("No shop status found, creating default (open)")
            default_status = {
                "is_open": True,
                "reopen_time": None,
                "reason": None,
                "updated_at": datetime.utcnow(),
                "updated_by": "system"
            }
            await db.insert_one("shop_status", default_status)
            status_doc = default_status
        
        # Serialize and send
        response = {
            "type": "shop_status",
            "is_open": status_doc.get("is_open", True),
            "reopen_time": status_doc.get("reopen_time"),
            "reason": status_doc.get("reason"),
            "updated_at": status_doc.get("updated_at", datetime.utcnow()).isoformat() if isinstance(status_doc.get("updated_at"), datetime) else str(status_doc.get("updated_at")),
            "updated_by": status_doc.get("updated_by", "admin")
        }
        
        logger.info(f"✅ Sending shop status: is_open={response['is_open']}")
        await websocket.send_json(response)
        
    except Exception as e:
        logger.error(f"❌ Error getting shop status: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to get shop status: {str(e)}"
        })


async def update_shop_status(websocket: WebSocket, data: dict, user_info: dict, db):
    """Update shop status (admin only)"""
    try:
        logger.info(f"📡 Updating shop status by {user_info.get('email')}")
        logger.info(f"Data received: {data}")
        
        is_open = data.get("is_open")
        reopen_time = data.get("reopen_time")
        reason = data.get("reason")
        
        if is_open is None:
            raise ValueError("is_open field is required")
        
        # Validate reopen_time if provided
        if reopen_time:
            try:
                reopen_datetime = datetime.fromisoformat(reopen_time.replace('Z', '+00:00'))
                if reopen_datetime <= datetime.utcnow():
                    await websocket.send_json({
                        "type": "error",
                        "message": "Reopen time must be in the future"
                    })
                    return
            except ValueError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid datetime format for reopen_time"
                })
                return
        
        # Prepare status document
        status_doc = {
            "is_open": bool(is_open),
            "reopen_time": reopen_time,
            "reason": reason,
            "updated_at": datetime.utcnow(),
            "updated_by": user_info.get("email", "admin")
        }
        
        # Update or insert
        existing = await db.find_one("shop_status", {})
        
        if existing:
            logger.info(f"Updating existing shop status document")
            await db.update_one(
                "shop_status",
                {"_id": existing["_id"]},
                {"$set": status_doc}
            )
        else:
            logger.info(f"Creating new shop status document")
            await db.insert_one("shop_status", status_doc)
        
        # Invalidate cache
        try:
            from app.cache.redis_manager import get_redis
            redis = get_redis()
            await redis.delete("shop_status")
            logger.info("✅ Cache invalidated")
        except Exception as cache_error:
            logger.warning(f"Cache invalidation failed: {cache_error}")
        
        # Send success response to admin
        response = {
            "type": "shop_status_updated",
            "is_open": bool(is_open),
            "reopen_time": reopen_time,
            "reason": reason,
            "message": f"Shop is now {'open' if is_open else 'closed'}",
            "updated_at": status_doc["updated_at"].isoformat(),
            "updated_by": user_info.get("email", "admin")
        }
        
        logger.info(f"✅ Shop status updated successfully: is_open={is_open}")
        await websocket.send_json(response)
        
        # ✅ Broadcast to all connected admins (optional)
        try:
            from admin.connection_manager import manager
            await manager.broadcast({
                "type": "shop_status_changed",
                "is_open": bool(is_open),
                "reopen_time": reopen_time,
                "reason": reason,
                "message": f"Shop status changed by {user_info.get('email')}"
            })
            logger.info("📢 Broadcast shop status change to all admins")
        except Exception as broadcast_error:
            logger.warning(f"Broadcast failed: {broadcast_error}")
        
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    except Exception as e:
        logger.error(f"❌ Error updating shop status: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to update shop status: {str(e)}"
        })