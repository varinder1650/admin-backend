from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
import logging
from app.services.order_service import OrderService
from app.utils.auth import current_active_user
from db.db_manager import DatabaseManager, get_database
from schema.order import OrderResponse, OrderResponseEnhanced
from schema.user import UserinDB
from app.utils.mongo import fix_mongo_types

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/")
async def create_order(
    order_data: dict,
    current_user: UserinDB = Depends(current_active_user),
    db: DatabaseManager = Depends(get_database)
):
    try:
        logger.info(f"Order creation request from user: {current_user.email}")
        logger.info(f"Order data received: {order_data}")
        
        order_service = OrderService(db)
        order_id = await order_service.create_order(order_data, current_user)

        logger.info(f"Order created successfully with ID: {order_id}")
        
        created_order = await db.find_one("orders", {"_id": ObjectId(order_id)})
        created_order['_id'] = str(created_order["_id"])
        created_order["user"] = str(created_order['user'])
        for item in created_order.get("items", []):
            if isinstance(item.get("product"), ObjectId):
                item["product"] = str(item["product"])

        return OrderResponse(**created_order)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create order error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create order"
        )

@router.get("/my")
async def get_my_orders(
    current_user: UserinDB = Depends(current_active_user),
    db: DatabaseManager = Depends(get_database)
):
    try:
        orders = await db.find_many(
            "orders", 
            {"user": ObjectId(current_user.id)},
            sort=[("created_at", -1)]
        )
        
        # Process each order to add product details
        for order in orders:
            if "items" in order and isinstance(order["items"], list):
                for item in order["items"]:
                    try:
                        # Handle both string and ObjectId product references
                        if isinstance(item.get('product'), str):
                            product_id = ObjectId(item['product'])
                        elif isinstance(item.get('product'), ObjectId):
                            product_id = item['product']
                            item['product'] = str(item['product'])  # Convert to string for Pydantic
                        else:
                            logger.warning(f"Invalid product reference in order {order.get('_id')}")
                            continue

                        # Fetch product details
                        product = await db.find_one("products", {"_id": product_id})
                        if product:
                            item["product_name"] = product["name"]
                            item["product_image"] = product.get("images", [])
                        else:
                            logger.warning(f"Product {product_id} not found for order {order.get('_id')}")
                            item["product_name"] = "Product not found"
                            item["product_image"] = []
                            
                    except Exception as item_error:
                        logger.error(f"Error processing item in order {order.get('_id')}: {item_error}")
                        # Set fallback values
                        item["product_name"] = "Error loading product"
                        item["product_image"] = []
                        continue
        
        # Apply MongoDB type fixes
        enhanced_orders = []
        for order in orders:
            try:
                fixed_order = fix_mongo_types(order)
                enhanced_orders.append(fixed_order)
            except Exception as order_error:
                logger.error(f"Error processing order {order.get('_id')}: {order_error}")
                continue

        # Use Pydantic model for validation and serialization
        validated_orders = []
        for order in enhanced_orders:
            try:
                validated_order = OrderResponseEnhanced(**order)
                validated_orders.append(validated_order)
            except Exception as validation_error:
                logger.error(f"Validation error for order {order.get('_id')}: {validation_error}")
                # Include the raw order if validation fails
                validated_orders.append(order)
                continue

        logger.info(f"Returning {len(validated_orders)} orders")
        return validated_orders
        
    except Exception as e:
        logger.error(f"Get my orders error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orders"
        )