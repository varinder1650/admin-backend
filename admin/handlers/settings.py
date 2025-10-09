from fastapi import WebSocket
import logging
from datetime import datetime, timedelta
from admin.utils.serialize import serialize_document

logger = logging.getLogger(__name__)

async def send_inventory_status(websocket: WebSocket, db):
    """Send inventory status"""
    try:
        low_stock_products = await db.find_many(
            "products",
            {"stock": {"$lt": 10}},
            sort=[("stock", 1)]
        )
        
        serialized_products = [serialize_document(product) for product in low_stock_products]
        
        await websocket.send_json({
            "type": "inventory_status",
            "low_stock_products": serialized_products,
            "total_products": await db.count_documents("products", {})
        })
    except Exception as e:
        logger.error(f"Error sending inventory status: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "Failed to fetch inventory status"
        })

async def handle_get_analytics(websocket: WebSocket, data: dict, db):
    """Get analytics data with orders for dashboard"""
    try:
        period = data.get("period", "week")
        filters = data.get("filters", {})
        
        logger.info(f"=== ANALYTICS REQUEST ===")
        logger.info(f"Period: {period}")
        logger.info(f"Filters: {filters}")
        
        # Calculate date range
        end_date = datetime.utcnow()
        if period == "day":
            start_date = end_date - timedelta(days=1)
        elif period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)

        logger.info(f"Date range: {start_date} to {end_date}")

        # Get all orders (not just for period) for dashboard
        logger.info("Fetching all orders...")
        all_orders = await db.find_many("orders", {}, sort=[("created_at", -1)])
        logger.info(f"Found {len(all_orders)} total orders")
        
        if len(all_orders) == 0:
            logger.warning("No orders found in database!")
            await websocket.send_json({
                "type": "analytics_data",
                "orders": [],
                "analytics": {
                    "period": period,
                    "total_orders": 0,
                    "total_revenue": 0,
                    "total_products": await db.count_documents("products", {}),
                    "total_users": await db.count_documents("users", {}),
                }
            })
            return
        
        # Serialize orders for frontend
        serialized_orders = []
        
        # Batch fetch users for order data
        user_ids = [order.get("user") for order in all_orders if order.get("user")]
        users_dict = {}
        if user_ids:
            logger.info(f"Fetching user data for {len(user_ids)} users...")
            users = await db.find_many("users", {"_id": {"$in": user_ids}})
            users_dict = {str(user["_id"]): user for user in users}
            logger.info(f"Found {len(users)} users")
        
        # Batch fetch delivery partners
        delivery_partner_ids = [order.get("delivery_partner") for order in all_orders 
                             if order.get("delivery_partner")]
        delivery_partners_dict = {}
        if delivery_partner_ids:
            partners = await db.find_many("users", {"_id": {"$in": delivery_partner_ids}})
            delivery_partners_dict = {str(partner["_id"]): partner for partner in partners}
        
        for order in all_orders:
            try:
                # Get user info
                user_id = str(order.get("user", ""))
                user = users_dict.get(user_id, {})
                
                # Get delivery partner info
                delivery_partner_id = str(order.get("delivery_partner", "")) if order.get("delivery_partner") else None
                delivery_partner = delivery_partners_dict.get(delivery_partner_id) if delivery_partner_id else None
                
                serialized_order = serialize_document(order)
                # Add frontend-friendly mappings
                serialized_order["id"] = serialized_order["_id"]
                serialized_order["total"] = serialized_order.get("total_amount", 0)
                serialized_order["status"] = serialized_order.get("order_status", "pending")
                serialized_order["user_name"] = user.get("name", "Unknown")
                serialized_order["user_email"] = user.get("email", "")
                serialized_order["user_phone"] = user.get("phone", "")
                serialized_order["delivery_partner_name"] = (
                    delivery_partner.get("name") if delivery_partner else None
                )
                
                serialized_orders.append(serialized_order)
            except Exception as e:
                logger.error(f"Error serializing order {order.get('_id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Serialized {len(serialized_orders)} orders")
        
        # Calculate analytics
        total_orders = len(serialized_orders)
        delivered_orders = [order for order in serialized_orders if order.get("status") == "delivered"]
        total_revenue = sum(order.get("total", 0) for order in delivered_orders)
        
        logger.info(f"Analytics calculated:")
        logger.info(f"  Total orders: {total_orders}")
        logger.info(f"  Delivered orders: {len(delivered_orders)}")
        logger.info(f"  Total revenue: {total_revenue}")
        
        response_data = {
            "type": "analytics_data",
            "orders": serialized_orders,
            "analytics": {
                "period": period,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "total_products": await db.count_documents("products", {}),
                "total_users": await db.count_documents("users", {}),
            }
        }
        
        logger.info(f"Sending response with {len(serialized_orders)} orders")
        await websocket.send_json(response_data)
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to fetch analytics: {str(e)}"
        })

async def get_pricing_config(websocket: WebSocket, db):
    """Get current pricing configuration"""
    try:
        # Try to get existing pricing config
        pricing_config = await db.find_one("pricing_config", {"active": True})
        # print(pricing_config)
        if not pricing_config:
            # Create default config if none exists
            default_config = {
                "deliveryFee": {
                    "type": "fixed",
                    "baseFee": 5.00,
                    "perKmRate": 1.50,
                    "minFee": 3.00,
                    "maxFee": 25.00,
                    "freeDeliveryThreshold": 50.00,
                },
                "appFee": {
                    "type": "percentage",
                    "value": 15.0,
                    "minFee": 1.00,
                    "maxFee": 20.00,
                },
                "active": True,
                "created_at": datetime.utcnow(),
                "created_by": "system"
            }
            # print(default_config)
            await db.insert_one("pricing_config", default_config)
            pricing_config = default_config
        
        pricing_config = serialize_document(pricing_config)
        # print("============================")
        # print(pricing_config)
        await websocket.send_json({
            "type": "pricing_config",
            "data": pricing_config
        })
        
    except Exception as e:
        logger.error(f"Error getting pricing config: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "Failed to fetch pricing configuration"
        })

async def update_pricing_config(websocket: WebSocket, data: dict, user_info: dict, db):
    """Update pricing configuration"""
    try:
        config_data = data.get("data", {})
        print("Received config_data:", config_data)
        
        if not config_data:
            await websocket.send_json({
                "type": "error", 
                "message": "No configuration data received"
            })
            return
        
        # Add metadata
        config_data.update({
            "active": True,
            "updated_at": datetime.utcnow(),
            "updated_by": user_info["email"]
        })

        price_id = await db.find_one("pricing_config",{"active":True})
        print(price_id)
        result = await db.update_one(
                "pricing_config",
                {"_id": price_id['_id']},
                {"$set": config_data}
            )

        if result:
            await websocket.send_json({
                "type": "pricing_updated",
                "message": "Pricing configuration updated successfully"
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Failed to update pricing configuration"
            })
            
    except Exception as e:
        logger.error(f"Error updating pricing config: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to update pricing: {str(e)}"
        })