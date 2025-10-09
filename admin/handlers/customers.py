from fastapi import WebSocket
import logging
from admin.utils.serialize import serialize_document

logger = logging.getLogger(__name__)

async def send_customers(websocket: WebSocket, db):
    """Send customer data"""
    try:
        # Add filter dict
        customers = await db.find_many("users", {"role": "user"}, limit=100)

        serialized_customers = [serialize_document(doc) for doc in customers]
        
        await websocket.send_json({
            "type": "customers_data",
            "customers": serialized_customers
        })
    except Exception as e:
        logger.error(f"Error sending customers: {e}")

async def get_customer_stats(db, start_date, end_date):
    """Get customer statistics"""
    # New customers
    new_customers = await db.count_documents(
        "users",
        {
            "role": "customer",
            "created_at": {"$gte": start_date, "$lte": end_date}
        }
    )
    
    # Active customers (made orders)
    pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start_date, "$lte": end_date}
            }
        },
        {
            "$group": {
                "_id": "$user_id"
            }
        },
        {
            "$count": "active_customers"
        }
    ]
    
    result = await db.aggregate("orders", pipeline)
    active_customers = result[0]["active_customers"] if result else 0
    
    return {
        "new_customers": new_customers,
        "active_customers": active_customers
    }