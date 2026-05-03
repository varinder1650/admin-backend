# admin-backend/admin/handlers/marketing.py
from fastapi import WebSocket
import logging
from datetime import datetime
from bson import ObjectId
from admin.utils.serialize import serialize_document
from admin.config.cloudinary_config import CloudinaryManager
from admin.connection_manager import manager
from admin.cache.redis_manager import get_redis

MARKETING_CACHE_KEY = "marketing:active_banners"

logger = logging.getLogger(__name__)


async def handle_get_marketing_banners(websocket: WebSocket, db):
    try:
        banners = await db.find_many("marketing_banners", {}, sort=[("order", 1)])
        serialized = [serialize_document(b) for b in banners]
        await websocket.send_json({"type": "marketing_banners_data", "banners": serialized})
    except Exception as e:
        logger.error(f"Error fetching marketing banners: {e}")
        await websocket.send_json({"type": "error", "message": "Failed to fetch marketing banners"})


async def handle_create_marketing_banner(websocket: WebSocket, data: dict, user_info: dict, db):
    try:
        user_email = (user_info or {}).get("email", "system")

        banner_image_data = data.get("image_data", "")
        image_url = ""
        if banner_image_data:
            result = await CloudinaryManager.upload_image(
                banner_image_data, folder="smartbag/marketing/banners"
            )
            if not result:
                await websocket.send_json({"type": "error", "message": "Banner image upload failed"})
                return
            image_url = result["secure_url"]

        containers = []
        for c in data.get("containers", []):
            container_image_url = ""
            container_image_data = c.get("image_data", "")
            if container_image_data:
                c_result = await CloudinaryManager.upload_image(
                    container_image_data, folder="smartbag/marketing/containers"
                )
                if c_result:
                    container_image_url = c_result["secure_url"]
            containers.append({
                "title": c.get("title", ""),
                "image_url": container_image_url,
                "bg_color": c.get("bg_color", "#FFFFFF"),
                "link_type": c.get("link_type", "none"),
                "link_value": c.get("link_value", ""),
            })

        doc = {
            "title": data.get("title", ""),
            "subtitle": data.get("subtitle", ""),
            "image_url": image_url,
            "bg_color": data.get("bg_color", "#FFFFFF"),
            "is_active": data.get("is_active", True),
            "order": int(data.get("order", 0)),
            "auto_rotate_interval": int(data.get("auto_rotate_interval", 4)),
            "containers": containers,
            "created_at": datetime.utcnow(),
            "created_by": user_email,
            "updated_at": datetime.utcnow(),
        }

        inserted_id = await db.insert_one("marketing_banners", doc)
        doc["_id"] = inserted_id
        await get_redis().delete(MARKETING_CACHE_KEY)
        await websocket.send_json({
            "type": "marketing_banner_created",
            "banner": serialize_document(doc),
        })
        await manager.broadcast(
            {"type": "marketing_banner_created", "banner": serialize_document(doc)},
            exclude=websocket,
        )
    except Exception as e:
        logger.error(f"Error creating marketing banner: {e}")
        await websocket.send_json({"type": "error", "message": "Failed to create marketing banner"})


async def handle_update_marketing_banner(websocket: WebSocket, data: dict, user_info: dict, db):
    try:
        banner_id = data.get("id") or data.get("_id")
        if not banner_id:
            await websocket.send_json({"type": "error", "message": "Banner ID required"})
            return

        existing = await db.find_one("marketing_banners", {"_id": ObjectId(banner_id)})
        if not existing:
            await websocket.send_json({"type": "error", "message": "Banner not found"})
            return

        update: dict = {"updated_at": datetime.utcnow()}

        for field in ("title", "subtitle", "bg_color", "is_active", "order", "auto_rotate_interval"):
            if field in data:
                update[field] = data[field]

        if "image_data" in data and data["image_data"]:
            result = await CloudinaryManager.upload_image(
                data["image_data"], folder="smartbag/marketing/banners"
            )
            if not result:
                await websocket.send_json({"type": "error", "message": "Banner image upload failed"})
                return
            update["image_url"] = result["secure_url"]

        if "containers" in data:
            containers = []
            for c in data["containers"]:
                container_image_url = c.get("image_url", "")
                if c.get("image_data"):
                    c_result = await CloudinaryManager.upload_image(
                        c["image_data"], folder="smartbag/marketing/containers"
                    )
                    if c_result:
                        container_image_url = c_result["secure_url"]
                containers.append({
                    "title": c.get("title", ""),
                    "image_url": container_image_url,
                    "bg_color": c.get("bg_color", "#FFFFFF"),
                    "link_type": c.get("link_type", "none"),
                    "link_value": c.get("link_value", ""),
                })
            update["containers"] = containers

        await db.update_one("marketing_banners", {"_id": ObjectId(banner_id)}, {"$set": update})
        updated = await db.find_one("marketing_banners", {"_id": ObjectId(banner_id)})
        await get_redis().delete(MARKETING_CACHE_KEY)

        await websocket.send_json({
            "type": "marketing_banner_updated",
            "banner": serialize_document(updated),
        })
        await manager.broadcast(
            {"type": "marketing_banner_updated", "banner": serialize_document(updated)},
            exclude=websocket,
        )
    except Exception as e:
        logger.error(f"Error updating marketing banner: {e}")
        await websocket.send_json({"type": "error", "message": "Failed to update marketing banner"})


async def handle_delete_marketing_banner(websocket: WebSocket, data: dict, db):
    try:
        banner_id = data.get("id") or data.get("_id")
        if not banner_id:
            await websocket.send_json({"type": "error", "message": "Banner ID required"})
            return

        existing = await db.find_one("marketing_banners", {"_id": ObjectId(banner_id)})
        if not existing:
            await websocket.send_json({"type": "error", "message": "Banner not found"})
            return

        await db.delete_one("marketing_banners", {"_id": ObjectId(banner_id)})
        await get_redis().delete(MARKETING_CACHE_KEY)

        await websocket.send_json({"type": "marketing_banner_deleted", "id": banner_id})
        await manager.broadcast(
            {"type": "marketing_banner_deleted", "id": banner_id}, exclude=websocket
        )
    except Exception as e:
        logger.error(f"Error deleting marketing banner: {e}")
        await websocket.send_json({"type": "error", "message": "Failed to delete marketing banner"})
