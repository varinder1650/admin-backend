from bson import ObjectId
from fastapi import WebSocket

from admin.utils.serialize import serialize_document
import logging

logger = logging.getLogger(__name__)

async def get_requests(websocket: WebSocket, filters:dict,db):
    try:
        requests = await db.find_many("product_requests",{},sort=[("created_at",-1)])
        
        for request in requests:
            # print(request)
            user_id = request["user_id"]
            user_data = await db.find_one("users",{"id": user_id})
            request['user_name'] = user_data["name"]
            request['email'] = user_data["email"]
            request['phone'] = user_data["phone"]
            # print(request)
        serialized_requests = [serialize_document(request) for request in requests]

        await websocket.send_json({
            "type": "suggestions_data",
            "suggestions": serialized_requests
        })
    except Exception as e:
        logger.error(f"Error getting the requests: {e}")
        raise e

async def update_requests_status(websocket: WebSocket, data:dict, db):
    try:
        # print(data)
        result = await db.find_one("product_requests",{"_id": ObjectId(data['suggestion_id'])})
        if not result:
            raise e
        updated_suggestion = await db.update_one("product_requests", {"_id": ObjectId(data['suggestion_id'])},{"status": data['status']})
        await websocket.send_json({
            "type": "suggestion_updated",
            "data": updated_suggestion
        })
    except Exception as e:
        logger.error(f"Failed to update the status of request: {e}")
        raise e